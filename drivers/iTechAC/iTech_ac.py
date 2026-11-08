import os
import re

from drivers.iTech.iTech import ITechPowerSupply


class UnsupportedInstrumentError(RuntimeError):
    """Raised when the connected instrument is not a model the driver supports."""


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
    """"""
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


def _parse_tagged_number(response):
    """Parses a reply that may repeat the phase first, such as "B,300.0" for PVOLtage? B."""
    return float(response.split(",")[-1])


def _parse_single_number(response, command):
    values = response.split(",")
    if len(values) != 1:
        raise ValueError(
            f"{command} returned {len(values)} values ({response.strip()!r}), as it does in "
            "three-phase mode; pass a phase, such as phase='A'")
    return float(values[0])


def _scpi_property(command, doc, to_scpi, from_scpi):
    """Builds a property that sends "<command> <value>" and queries "<command>?"."""

    def getter(self):
        return from_scpi(self.query(f"{command}?"))

    def setter(self, value):
        self.write(f"{command} {to_scpi(value)}")

    return property(getter, setter, doc=doc)


_OUTPUT_MODE = _Choice("AC", "DC", "ACDC", "DCAC")
_PHASE_MODE = _Choice("ONE", "THRee", "DIFFerence", "MULTichannel")
_PHASE = _Choice("A", "B", "C")
_ANGLE_PAIR = _Choice("BA", "CA")
_LINE_PAIR = _Choice("BA", "CA", "CB")
_SURGE_SAG_PHASES = _Choice("A", "B", "C", "AB", "AC", "BC", "ABC")
_SURGE_SAG_PHASE_SYNC = _Choice("SYNC", "SPEC")
_SURGE_SAG_MODE = _Choice("PERiod", "TRIG")
_SURGE_SAG_ACTION = _Choice("IMMediate", "PHASe")
_SURGE_SAG_TRIGGER_SOURCE = _Choice("IMMediate", "MANual", "BUS", "TRIG1", "TRIG2")
_SURGE_SAG_VALUE_SELECT = _Choice("PERCent", "SETTing")


class ITechACPowerSupply(ITechPowerSupply):
    """
    Extension of ITechPowerSupply which includes AC-specific modes and commanding, intended for IT7900EP.

    Grid simulation commands are taken from the IT7900P Series Programming Guide V1.0
    (Manuals/IT7900P_Programming_Guide-EN.pdf).

    Single-phase and three-phase operation are supported. In three-phase mode, settings
    without a phase argument, such as voltage, frequency and the output impedance, apply
    to all three phases; use the phase methods to address one phase. Multi-channel mode's
    channel arguments are not exposed, and Surge/Sag is not supported in that mode.

    connect() checks the *IDN? reply and raises UnsupportedInstrumentError, after
    disconnecting, unless the instrument is an IT7900EP series model.
    """
    # Matches models such as IT7942EP-350-210, but not IT7900P models such as IT7942P-350-210
    SUPPORTED_MODEL = re.compile(r"IT79\d\dEP(-|$)")

    @classmethod
    def is_supported(cls, identity):
        """Returns whether an *IDN? reply identifies an IT7900EP series instrument."""
        fields = identity.split(",")
        return len(fields) > 1 and cls.SUPPORTED_MODEL.match(fields[1].strip()) is not None

    def connect(self):
        """Connects, then raises UnsupportedInstrumentError unless the instrument is an IT7900EP."""
        super().connect()
        identity = self.id
        if not self.is_supported(identity):
            self.disconnect()
            raise UnsupportedInstrumentError(
                f"{type(self).__name__} supports IT7900EP series instruments only, "
                f"but *IDN? returned {identity.strip()!r}")

    # --- Phase configuration (guide chapters 4 and 12) ---

    phase_mode = _scpi_property(
        "SYSTEM:FUNCTION",
        "Power supply phase mode: 'ONE' (single-phase), 'THREE' (three-phase), "
        "'DIFFERENCE' (reverse phase) or 'MULTICHANNEL'. *RST: ONE.",
        _PHASE_MODE, _PHASE_MODE)

    balanced = _scpi_property(
        "OUTPUT:BALANCE",
        "In three-phase mode, whether the phases are balanced (True) or can be set "
        "separately (False). Phase angles only take effect when unbalanced.",
        _on_off, _parse_bool)

    def phase_voltage(self, phase):
        """Queries the AC voltage setpoint of phase 'A', 'B' or 'C', in volts."""
        return _parse_tagged_number(self.query(f"PVOLTAGE? {_PHASE(phase)}"))

    def set_phase_voltage(self, phase, volts):
        """Sets the AC voltage of phase 'A', 'B' or 'C', in volts."""
        self.write(f"PVOLTAGE {_PHASE(phase)},{_number(volts)}")

    def phase_angle(self, pair):
        """Queries the angle of phase B ('BA') or C ('CA') relative to phase A, in degrees."""
        return _parse_tagged_number(self.query(f"ANGLE:DIFFERENCE? {_ANGLE_PAIR(pair)}"))

    def set_phase_angle(self, pair, degrees):
        """Sets the angle of phase B ('BA') or C ('CA') relative to phase A, in degrees.

        Only takes effect in three-phase mode with balanced set to False.
        """
        self.write(f"ANGLE:DIFFERENCE {_ANGLE_PAIR(pair)},{_number(degrees)}")

    # --- Measurements (guide chapter 14) ---

    def read_voltage(self, phase=None):
        """Measures the RMS output voltage, in volts.

        In three-phase mode, pass phase 'A', 'B' or 'C'. Without a phase, the instrument
        replies with all three values, and this raises ValueError.
        """
        return self._read_phase_value("MEASURE:VOLTAGE?", phase)

    def read_current(self, phase=None):
        """Measures the RMS output current, in amps.

        In three-phase mode, pass phase 'A', 'B' or 'C'. Without a phase, the instrument
        replies with all three values, and this raises ValueError.
        """
        return self._read_phase_value("MEASURE:CURRENT?", phase)

    def read_line_voltage(self, pair):
        """Measures the line-to-line voltage between phases 'BA', 'CA' or 'CB', in volts."""
        return float(self.query(f"MEASURE:LTLVOLTAGE? {_LINE_PAIR(pair)}"))

    def _read_phase_value(self, command, phase):
        if phase is not None:
            command = f"{command} {_PHASE(phase)}"
        return _parse_single_number(self.query(command), command)

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

    surge_sag_phases = _scpi_property(
        "SURGESAG:PHASE:ENABLE",
        "In three-phase mode, which phases the surge/sag affects: 'A', 'B', 'C', 'AB', "
        "'AC', 'BC' or 'ABC'.",
        _SURGE_SAG_PHASES, _SURGE_SAG_PHASES)

    surge_sag_phase_sync = _scpi_property(
        "SURGESAG:ANGLE:ENABLE",
        "In three-phase mode, 'SYNC' starts the surge/sag on all phases together; 'SPEC' "
        "starts it at each phase's own start angle.",
        _SURGE_SAG_PHASE_SYNC, _SURGE_SAG_PHASE_SYNC)

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
