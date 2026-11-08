import os

from drivers.iTech.iTech import ITechPowerSupply


class _Choice:
    """Validates a SCPI keyword argument and normalizes it to its long form.

    Keywords use the SCPI manual notation, where the upper-case letters are the short
    form: "PERiod" accepts "PER" or "PERIOD" in any case, and both become "PERIOD".
    """

    def __init__(self, *keywords):
        self._long_forms = {}
        for keyword in keywords:
            long_form = keyword.upper()
            short_form = "".join(c for c in keyword if c.isupper() or c.isdigit())
            self._long_forms[long_form] = long_form
            self._long_forms[short_form] = long_form

    def __call__(self, value):
        key = str(value).strip().strip('"').upper()
        if key not in self._long_forms:
            raise ValueError(f"must be one of {sorted(set(self._long_forms.values()))}, got {value!r}")
        return self._long_forms[key]


def _number(value):
    return str(float(value))


def _integer(value):
    if int(value) != value:
        raise ValueError(f"must be a whole number, got {value!r}")
    return str(int(value))


def _on_off(value):
    return "ON" if value else "OFF"


def _parse_bool(response):
    return response.strip().upper() in ("1", "ON")


def _parse_integer(response):
    return int(float(response))


def _scpi_property(command, doc, to_scpi, from_scpi):
    """Builds a property that sends "<command> <value>" and queries "<command>?"."""

    def getter(self):
        return from_scpi(self.query(f"{command}?"))

    def setter(self, value):
        self.write(f"{command} {to_scpi(value)}")

    return property(getter, setter, doc=doc)


_OUTPUT_MODE = _Choice("AC", "DC", "ACDC", "DCAC")
_SURGE_SAG_MODE = _Choice("PERiod", "TRIG")
_SURGE_SAG_ACTION = _Choice("IMMediate", "PHASe")
_SURGE_SAG_TRIGGER_SOURCE = _Choice("IMMediate", "MANual", "BUS", "TRIG1", "TRIG2")
_SURGE_SAG_VALUE_SELECT = _Choice("PERCent", "SETTing")


class ITechACPowerSupply(ITechPowerSupply):
    """
    Extension of ITechPowerSupply which includes AC-specific modes and commanding, intended for IT7900EP.

    Grid simulation commands are taken from the IT7900P Series Programming Guide V1.0
    (Manuals/IT7900P_Programming_Guide-EN.pdf) and address a single-phase output. The
    optional phase and channel arguments for three-phase and multi-channel use are not
    exposed. Surge/Sag is not supported in multi-channel mode.
    """
    # --- Output mode (guide chapter 11) ---

    mode = _scpi_property(
        "FUNCTION",
        "Output mode: 'AC', 'DC', 'ACDC' or 'DCAC'. Three-phase mode allows only 'AC' "
        "and 'ACDC'. *RST: AC.",
        _OUTPUT_MODE, _OUTPUT_MODE)

    # --- Grid frequency (guide chapter 11) ---

    frequency = _scpi_property(
        "FREQUENCY", "Output frequency in Hz. *RST: 50 Hz.", _number, float)

    # --- Programmable output impedance, to simulate the grid's R and L (guide chapter 12) ---

    impedance_enabled = _scpi_property(
        "OUTPUT:IMPEDANCE",
        "Whether the programmable output impedance is on (True) or off (False).",
        _on_off, _parse_bool)

    impedance_resistance = _scpi_property(
        "OUTPUT:IMPEDANCE:RESISTANCE:LEVEL",
        "Output impedance resistance. Takes effect once impedance_enabled is True. "
        "The guide does not state its unit.",
        _number, float)

    impedance_inductance = _scpi_property(
        "OUTPUT:IMPEDANCE:INDUCTANCE:LEVEL",
        "Output impedance inductance. The guide does not state its unit.",
        _number, float)

    # --- Surge/Sag voltage disturbances (guide chapters 5, 6, 8 and 17) ---

    surge_sag_mode = _scpi_property(
        "SURGESAG:MODE",
        "'PERIOD' repeats the surge/sag periodically; 'TRIG' runs it when triggered.",
        _SURGE_SAG_MODE, _SURGE_SAG_MODE)

    surge_sag_action = _scpi_property(
        "SURGESAG:ACTION",
        "In 'TRIG' mode, start 'IMMEDIATE'ly or at surge_sag_start_phase ('PHASE'). "
        "*RST: IMMEDIATE.",
        _SURGE_SAG_ACTION, _SURGE_SAG_ACTION)

    surge_sag_trigger_source = _scpi_property(
        "TRIGGER:SURGESAG:SOURCE",
        "Trigger source: 'IMMEDIATE', 'MANUAL', 'BUS', 'TRIG1' or 'TRIG2'.",
        _SURGE_SAG_TRIGGER_SOURCE, _SURGE_SAG_TRIGGER_SOURCE)

    surge_sag_start_phase = _scpi_property(
        "SURGESAG:PHASE:START", "Phase angle where the surge/sag starts, in degrees. *RST: 0.",
        _number, float)

    surge_sag_phase_width = _scpi_property(
        "SURGESAG:PHASE:WIDTH", "Angular width of the surge/sag, in degrees. *RST: 0.",
        _number, float)

    surge_sag_symmetry = _scpi_property(
        "SURGESAG:SYMMETRY", "Whether symmetry mode is on. *RST: False.",
        _on_off, _parse_bool)

    surge_sag_repeat_count = _scpi_property(
        "SURGESAG:REPEAT:COUNT", "Number of consecutive surge/sag events. *RST: 1.",
        _integer, _parse_integer)

    surge_sag_period_count = _scpi_property(
        "SURGESAG:PERIOD:COUNT", "Interval between surge/sag events, in periods. *RST: 1.",
        _integer, _parse_integer)

    surge_sag_value_select = _scpi_property(
        "SURGESAG:VALUE:SELECT",
        "Whether the disturbance level comes from surge_sag_percent ('PERCENT') or "
        "surge_sag_value ('SETTING'). *RST: PERCENT.",
        _SURGE_SAG_VALUE_SELECT, _SURGE_SAG_VALUE_SELECT)

    surge_sag_percent = _scpi_property(
        "SURGESAG:VALUE:PERCENT", "Disturbance level as a percentage. *RST: 0.",
        _number, float)

    surge_sag_value = _scpi_property(
        "SURGESAG:VALUE", "Disturbance level in volts. *RST: 0.",
        _number, float)

    def start_surge_sag(self):
        """Starts the surge/sag function, which then runs or waits for its trigger."""
        self.write("INITIATE:SURGESAG")

    def abort_surge_sag(self):
        """Stops the surge/sag function."""
        self.write("ABORT:SURGESAG")

    def force_trigger(self):
        """Sends a software trigger."""
        self.write("TRIGGER:FORCE")

    def surge_sag_state(self):
        """Queries the surge/sag running state. The guide does not document the response format."""
        return self.query("SURGESAG:STATE?")


if __name__ == "__main__":
    # Locate the simulation file next to this script, regardless of the working directory
    sim_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation.yaml")
    SIMULATED_BACKEND = f"{sim_file}@sim"
    SIMULATED_RESOURCE = "TCPIP0::192.168.1.100::5025::SOCKET"

    print(f"Initializing virtual interface for: {SIMULATED_RESOURCE}...")
    power_supply = ITechACPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND)

    try:
        # Open communication channel
        power_supply.connect()

        print("\n--- Testing Inherited Voltage Setter & Getter ---")
        power_supply.voltage = 12.5
        voltage = power_supply.voltage
        print(f"Configured Voltage level: {voltage} V")
        assert float(voltage) == 12.5

        print("\n--- Testing Output Mode Setter & Getter ---")
        default_mode = power_supply.mode
        print(f"Default Output Mode: {default_mode}")
        assert default_mode == "AC"

        for target_mode in ("DC", "AC"):
            power_supply.mode = target_mode
            mode = power_supply.mode
            print(f"Current Output Mode: {mode}")
            assert mode == target_mode

        print("\n--- Testing Grid Frequency Setter & Getter ---")
        power_supply.frequency = 60
        frequency = power_supply.frequency
        print(f"Configured Frequency: {frequency} Hz")
        assert frequency == 60.0

        print("\nAll simulated instrument checks passed.")

    finally:
        power_supply.disconnect()
        print("\nVirtual resource channel safely released.")
