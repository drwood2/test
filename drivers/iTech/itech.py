"""Driver implementation for iTech power supplies"""
import os
import easy_scpi as scpi

from drivers.scpi_helpers import Choice, parse_bool, scpi_property, to_number

_PRIORITY_MODE = Choice("VOLTage", "CURRent")


def _load_only_error(action):
    return ValueError(
        f"{action} while load_only is True; "
        "create the power supply with load_only=False to allow power output")


class ITechPowerSupply(scpi.Instrument):
    """
    Power supply driver intended specifically for high-current power supplies
    Args:
        resource_string: ip connection, TCPIP0::192.168.200.100::30000::SOCKET by default
        backend: .yaml file which mocks expected replies for simulation
        load_only: restrict setups to no power output for protection

    The load simulation commands follow the IT6600C Series Programming Guide V1.0
    (Manuals/IT6600C_Programming_Guide-EN.pdf) and User Manual section 4.1.1. With
    load_only True, settings that only sink power are allowed, and settings that could
    source power are blocked.
    """
    load_only=True
    def __init__(self, resource_string, backend="", load_only=True):
        # An empty backend uses real hardware; "<file>.yaml@sim" uses pyvisa-sim
        super().__init__(
            port=resource_string,
            backend=backend,
            port_match=False,  # disabling necessary for pyvisa-sim support
            timeout=5000,
            read_termination='\n',
            write_termination='\n'
        )
        self.load_only=load_only

    @property
    def voltage(self):
        """Queries the source voltage using easy-scpi property tree mapping."""
        return float(self.source.voltage())

    @voltage.setter
    def voltage(self, volts):
        """Sets the source voltage."""
        if self.load_only:
            raise ValueError(
                "voltage cannot be set while load_only is True; "
                "create the power supply with load_only=False to allow power output")
        self.source.voltage(volts)

    @property
    def output_state(self):
        """Queries whether the output is enabled: True (on) or False (off).

        The IT6600C replies "1" or "0"; "ON" and "OFF" are also accepted, as the
        IT7900P Programming Guide allows either.
        """
        reply = self.output().strip().upper()
        if reply in ("1", "ON"):
            return True
        if reply in ("0", "OFF"):
            return False
        raise ValueError(f"unexpected OUTPUT? reply {reply!r}; expected 1, 0, ON or OFF")

    @output_state.setter
    def output_state(self, state):
        """Enables (True, 1 or 'ON') or disables (False, 0 or 'OFF') the output.

        Enabling raises ValueError while load_only is True; disabling is always allowed.
        """
        key = state.strip().upper() if isinstance(state, str) else state
        if key in (True, "1", "ON"):
            if self.load_only:
                raise ValueError(
                    "output cannot be turned on while load_only is True; "
                    "create the power supply with load_only=False to allow power output")
            self.output("1")
        elif key in (False, "0", "OFF"):
            self.output("0")
        else:
            raise ValueError(f"output_state must be True, False, 1, 0, 'ON' or 'OFF', got {state!r}")

    def read_current(self):
        """Fetches dynamic simulated measurement readings."""
        return float(self.measure.current())

    # --- Load simulation (Programming Guide chapter 3, User Manual 4.1.1) ---

    priority_mode = scpi_property(
        "FUNCTION",
        "Priority mode: 'VOLTAGE' (CV priority) or 'CURRENT' (CC priority). "
        "Only-load mode needs 'CURRENT'. *RST: VOLTAGE.",
        _PRIORITY_MODE, _PRIORITY_MODE)

    @property
    def only_load_mode(self):
        """Whether the instrument's own only-load mode is on, so it can sink but not source.

        This is the instrument setting FUNCtion:ILOad, separate from the driver's load_only
        flag. It needs priority_mode 'CURRENT'; enter_only_load_mode() sets both.

        In CV priority this returns False without asking: only-load mode can't be on there,
        and a real IT6600C doesn't answer FUNCTION:ILOAD? in CV priority (the query times
        out and logs -200 "Execution error").
        """
        if self.priority_mode != "CURRENT":
            return False
        return parse_bool(self.query("FUNCTION:ILOAD?"))

    @only_load_mode.setter
    def only_load_mode(self, enabled):
        if not enabled and self.load_only:
            raise _load_only_error("only-load mode cannot be turned off")
        self.write(f"FUNCTION:ILOAD {1 if enabled else 0}")

    def enter_only_load_mode(self):
        """Sets CC priority, then turns on only-load mode, in the User Manual's order."""
        self.priority_mode = "CURRENT"
        self.only_load_mode = True

    @property
    def current(self):
        """Current setpoint Is in CC priority, in amps. Negative values sink current."""
        return float(self.query("CURRENT?"))

    @current.setter
    def current(self, amps):
        amps = float(amps)
        if amps > 0 and self.load_only:
            raise _load_only_error("a positive current, which sources power, cannot be set")
        self.write(f"CURRENT {to_number(amps)}")

    resistance = scpi_property(
        "RESISTANCE",
        "Internal (series) resistance in ohms, CV priority only. It is not a "
        "constant-resistance load: a real IT6600C accepts 0 to 0.6 ohms, rejects it in CC "
        "priority (-200 \"Execution error\"), and rejected 0.3 ohms with -20807 \"Config "
        "execute fail\", so it may need another setting enabled first. *RST: 0.",
        to_number, float)

    power = scpi_property(
        "POWER",
        "Power setpoint in watts. In only-load mode it sets P-, the constant-power load, "
        "which must be negative (a positive value fails with 120 \"Parameter overflowed\"); "
        "otherwise it sets P+. *RST: rated power.",
        to_number, float)

    current_limit = scpi_property(
        "CURRENT:LIMIT",
        "Upper current limit I+ in CV priority, in amps.",
        to_number, float)

    current_limit_negative = scpi_property(
        "CURRENT:LIMIT:NEGATIVE",
        "Lower current limit I- in amps, negative: the most current it sinks. CV priority "
        "only; a real IT6600C rejects it in CC priority (-200 \"Execution error\").",
        to_number, float)

    power_limit = scpi_property(
        "POWER:LIMIT", "Upper power limit P+, in watts.", to_number, float)

    power_limit_negative = scpi_property(
        "POWER:LIMIT:NEGATIVE",
        "Lower power limit P-, in watts: the most power it sinks.",
        to_number, float)

    def read_voltage(self):
        """Measures the output voltage, in volts."""
        return float(self.query("MEASURE:VOLTAGE?"))

    def read_power(self):
        """Measures the output power, in watts."""
        return float(self.query("MEASURE:POWER?"))

if __name__ == "__main__":
    # Locate the simulation file next to this script, regardless of the working directory
    sim_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation.yaml")
    SIMULATED_BACKEND = f"{sim_file}@sim"
    SIMULATED_RESOURCE = "TCPIP0::192.168.200.100::30000::SOCKET"

    print(f"Initializing virtual interface for: {SIMULATED_RESOURCE}...")
    # load_only=False so the setter checks below can set the voltage
    power_supply = ITechPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND, load_only=False)

    try:
        # Open communication channel
        power_supply.connect()

        # Verify baseline communication
        print("\n--- Testing Basic Identification ---")
        identity = power_supply.id
        print(f"Instrument IDN: {identity}")
        assert identity == "Itech Electronics,IT6642C-1200-200,800000000000000001,000.001.038,83.R,13.R"

        print("\n--- Testing Target Setters & Getters ---")
        power_supply.voltage = 12.5
        voltage = power_supply.voltage
        print(f"Configured Voltage level: {voltage} V")
        assert float(voltage) == 12.5

        power_supply.output_state = "ON"
        output_state = power_supply.output_state
        print(f"Current Output Condition: {output_state}")
        assert output_state is True

        print("\n--- Reading Virtual Measurements ---")
        current_reading = power_supply.read_current()
        print(f"Measured Current Draw: {current_reading} A")
        assert float(current_reading) == 1.234

        print("\n--- Testing load_only Protection ---")
        power_supply.load_only = True
        try:
            power_supply.voltage = 24.0
        except ValueError:
            print("Setting voltage with load_only=True raised ValueError, as expected")
        else:
            raise AssertionError("Setting voltage with load_only=True did not raise ValueError")
        voltage = power_supply.voltage
        print(f"Voltage after blocked setting: {voltage} V")
        assert voltage == 12.5, "the blocked setting must not reach the instrument"

        print("\nAll simulated instrument checks passed.")

    finally:
        power_supply.disconnect()
        print("\nVirtual resource channel safely released.")