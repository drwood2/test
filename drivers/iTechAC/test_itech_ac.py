"""Test file for iTechAC driver"""
from pathlib import Path

import pytest

from drivers.iTechAC.itech_ac import ITechACPowerSupply, UnsupportedInstrumentError

SIMULATED_BACKEND = f"{Path(__file__).with_name('simulation.yaml')}@sim"
# The parent driver's simulation identifies as an IT6600C
IT6600C_BACKEND = f"{Path(__file__).parents[1] / 'iTech' / 'simulation.yaml'}@sim"
SIMULATED_RESOURCE = "TCPIP0::192.168.200.100::30000::SOCKET"


@pytest.fixture
def power_supply():
    instrument = ITechACPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND)
    instrument.connect()
    yield instrument
    instrument.disconnect()


def test_connect_accepts_an_it7900ep(power_supply):
    assert power_supply.connected
    assert power_supply.id.split(",")[1] == "IT7942EP-350-210"


def test_connect_rejects_an_it6600c_and_disconnects():
    instrument = ITechACPowerSupply(SIMULATED_RESOURCE, backend=IT6600C_BACKEND)
    with pytest.raises(UnsupportedInstrumentError, match="IT6642C-1200-200"):
        instrument.connect()
    assert not instrument.connected


@pytest.mark.parametrize("identity, supported", [
    ("Itech Electronics,IT7942EP-350-210,800000000000000002,000.001.038,83.R,13.R", True),
    ("Itech Electronics, IT7906EP-350-90, 800000000000000003, 000.001.038", True),
    ("Itech Electronics,IT7984EP-350-420,800000000000000004,000.001.038\n", True),
    ("Itech Electronics,IT7942P-350-210,800000000000000005,000.001.038", False),
    ("Itech Electronics,IT6642C-1200-200,800000000000000001,000.001.038", False),
    ("Itech Electronics,IT8215-350-90,804947011767740001,000.001.038", False),
    ("IT7942EP-350-210", False),
    ("", False),
])
def test_is_supported(identity, supported):
    assert ITechACPowerSupply.is_supported(identity) is supported


def test_enable_ac_mode_then_disable_output(power_supply):
    # Start away from the simulator defaults (AC, OFF) so the checks below prove a change
    power_supply.load_only = False  # turning the output on needs load_only off
    power_supply.mode = "DC"
    power_supply.output_state = "ON"
    assert power_supply.mode == "DC"
    assert power_supply.output_state is True

    power_supply.mode = "AC"
    assert power_supply.mode == "AC"

    power_supply.output_state = "OFF"
    assert power_supply.output_state is False


@pytest.mark.parametrize("mode", ["DC", "ACDC", "DCAC", "AC"])
def test_all_output_modes(power_supply, mode):
    power_supply.mode = mode
    assert power_supply.mode == mode


def test_grid_defaults_match_documented_reset_values(power_supply):
    assert power_supply.frequency == 50.0
    assert power_supply.impedance_enabled is False
    assert power_supply.impedance_resistance == 0.0
    assert power_supply.impedance_inductance == 0.0
    assert power_supply.surge_sag_mode == "PERIOD"
    assert power_supply.surge_sag_action == "IMMEDIATE"
    assert power_supply.surge_sag_trigger_source == "MANUAL"
    assert power_supply.surge_sag_start_phase == 0.0
    assert power_supply.surge_sag_phase_width == 0.0
    assert power_supply.surge_sag_symmetry is False
    assert power_supply.surge_sag_repeat_count == 1
    assert power_supply.surge_sag_period_count == 1
    assert power_supply.surge_sag_value_select == "PERCENT"
    assert power_supply.surge_sag_percent == 0.0
    assert power_supply.surge_sag_value == 0.0


def test_voltage_reads_one_float_per_phase(power_supply):
    # The simulator replies like the three-phase bench unit, such as "0.00,0.00,0.00"
    assert power_supply.voltage == (0.0, 0.0, 0.0)

    power_supply.load_only = False
    power_supply.voltage = 277
    voltage = power_supply.voltage
    assert voltage == (277.0, 277.0, 277.0)
    assert type(voltage) is tuple
    assert all(type(volts) is float for volts in voltage)


def test_setting_voltage_keeps_the_load_only_guard(power_supply):
    with pytest.raises(ValueError, match="load_only"):
        power_supply.voltage = 277
    assert power_supply.voltage == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("name, number_type", [
    ("frequency", float),
    ("impedance_resistance", float),
    ("impedance_inductance", float),
    ("surge_sag_start_phase", float),
    ("surge_sag_phase_width", float),
    ("surge_sag_repeat_count", int),
    ("surge_sag_period_count", int),
    ("surge_sag_percent", float),
    ("surge_sag_value", float),
])
def test_numeric_settings_return_numbers(power_supply, name, number_type):
    assert type(getattr(power_supply, name)) is number_type


def test_read_current_returns_a_number(power_supply):
    assert power_supply.read_current() == 1.234


def test_frequency(power_supply):
    assert power_supply.frequency == 50.0

    power_supply.frequency = 60
    assert power_supply.frequency == 60.0


def test_output_impedance(power_supply):
    assert power_supply.impedance_enabled is False

    power_supply.impedance_enabled = True
    power_supply.impedance_resistance = 0.4
    power_supply.impedance_inductance = 1.5
    assert power_supply.impedance_enabled is True
    assert power_supply.impedance_resistance == 0.4
    assert power_supply.impedance_inductance == 1.5


def test_surge_sag_configuration(power_supply):
    # A triggered 50% sag lasting half a cycle, starting at 90 degrees, three times
    power_supply.surge_sag_mode = "TRIG"
    power_supply.surge_sag_action = "PHASE"
    power_supply.surge_sag_trigger_source = "BUS"
    power_supply.surge_sag_start_phase = 90
    power_supply.surge_sag_phase_width = 180
    power_supply.surge_sag_symmetry = True
    power_supply.surge_sag_repeat_count = 3
    power_supply.surge_sag_period_count = 2
    power_supply.surge_sag_value_select = "PERCENT"
    power_supply.surge_sag_percent = 50
    power_supply.surge_sag_value = 115

    assert power_supply.surge_sag_mode == "TRIG"
    assert power_supply.surge_sag_action == "PHASE"
    assert power_supply.surge_sag_trigger_source == "BUS"
    assert power_supply.surge_sag_start_phase == 90.0
    assert power_supply.surge_sag_phase_width == 180.0
    assert power_supply.surge_sag_symmetry is True
    assert power_supply.surge_sag_repeat_count == 3
    assert power_supply.surge_sag_period_count == 2
    assert power_supply.surge_sag_value_select == "PERCENT"
    assert power_supply.surge_sag_percent == 50.0
    assert power_supply.surge_sag_value == 115.0


def test_surge_sag_keywords_accept_short_forms(power_supply):
    power_supply.surge_sag_mode = "per"
    power_supply.surge_sag_trigger_source = "Man"
    assert power_supply.surge_sag_mode == "PERIOD"
    assert power_supply.surge_sag_trigger_source == "MANUAL"


@pytest.mark.parametrize("name, value", [
    ("mode", "ACAC"),
    ("surge_sag_mode", "ONCE"),
    ("surge_sag_trigger_source", "TRIG3"),
    ("surge_sag_repeat_count", 2.5),
])
def test_invalid_settings_are_rejected(power_supply, name, value):
    with pytest.raises(ValueError):
        setattr(power_supply, name, value)


def test_phase_mode(power_supply):
    assert power_supply.phase_mode == "THREE"

    power_supply.phase_mode = "ONE"
    assert power_supply.phase_mode == "ONE"

    power_supply.phase_mode = "thr"
    assert power_supply.phase_mode == "THREE"


def test_unbalanced_three_phase_setpoints(power_supply):
    power_supply.phase_mode = "THREE"
    power_supply.balanced = False
    assert power_supply.balanced is False

    for phase, volts in (("A", 230), ("B", 207), ("C", 253.5)):
        power_supply.set_phase_voltage(phase, volts)
    power_supply.set_phase_angle("BA", 110)
    power_supply.set_phase_angle("CA", 250)

    # PVOLTAGE? replies with the phase first, such as "B,207.00"
    assert power_supply.phase_voltage("A") == 230.0
    assert power_supply.phase_voltage("b") == 207.0
    assert power_supply.phase_voltage("C") == 253.5
    assert type(power_supply.phase_voltage("A")) is float
    assert power_supply.phase_angle("BA") == 110.0
    assert power_supply.phase_angle("CA") == 250.0


def test_per_phase_measurements(power_supply):
    assert power_supply.read_voltage("A") == 220.1
    assert power_supply.read_voltage("B") == 219.9
    assert power_supply.read_voltage("C") == 220.3
    assert power_supply.read_current("A") == 1.1
    assert power_supply.read_current("C") == 1.3
    assert power_supply.read_line_voltage("CB") == 380.9


def test_three_phase_reading_without_a_phase_raises(power_supply):
    # The simulator replies to MEASURE:VOLTAGE? with three values, as a three-phase instrument does
    with pytest.raises(ValueError, match="pass a phase"):
        power_supply.read_voltage()


def test_surge_sag_three_phase_settings(power_supply):
    assert power_supply.surge_sag_phases == "ABC"
    assert power_supply.surge_sag_phase_sync == "SYNC"

    power_supply.surge_sag_phases = "BC"
    power_supply.surge_sag_phase_sync = "SPEC"
    assert power_supply.surge_sag_phases == "BC"
    assert power_supply.surge_sag_phase_sync == "SPEC"


@pytest.mark.parametrize("call", [
    lambda psu: psu.set_phase_voltage("D", 230),
    lambda psu: psu.phase_voltage("AB"),
    lambda psu: psu.set_phase_angle("CB", 120),
    lambda psu: psu.read_current("N"),
    lambda psu: psu.read_line_voltage("AA"),
    lambda psu: setattr(psu, "phase_mode", "TWO"),
    lambda psu: setattr(psu, "surge_sag_phases", "ABCD"),
])
def test_invalid_phase_arguments_are_rejected(power_supply, call):
    with pytest.raises(ValueError):
        call(power_supply)


def test_surge_sag_run_commands(power_supply):
    power_supply.start_surge_sag()
    power_supply.force_trigger()
    assert power_supply.surge_sag_state() == "0"
    power_supply.abort_surge_sag()


# --- Inherited IT6600C settings that would send FUNCTION or CURRENT commands ---

@pytest.fixture
def sent_commands(power_supply, monkeypatch):
    """Records every command the driver sends, while still sending it to the simulator."""
    sent = []
    write, query = power_supply.write, power_supply.query
    monkeypatch.setattr(power_supply, "write", lambda msg: (sent.append(msg), write(msg))[1])
    monkeypatch.setattr(power_supply, "query", lambda msg: (sent.append(msg), query(msg))[1])
    return sent


@pytest.mark.parametrize("name, value", [
    ("priority_mode", "CURRENT"),
    ("only_load_mode", True),
    ("current", -10),
    ("current_limit", 5),
    ("current_limit_negative", -5),
])
def test_it6600c_settings_are_blocked_without_sending_anything(power_supply, sent_commands, name, value):
    with pytest.raises(NotImplementedError, match="IT7900EP"):
        getattr(power_supply, name)
    with pytest.raises(NotImplementedError, match="IT7900EP"):
        setattr(power_supply, name, value)
    assert sent_commands == []


def test_enter_only_load_mode_is_blocked_without_sending_anything(power_supply, sent_commands):
    with pytest.raises(NotImplementedError, match="IT7900EP"):
        power_supply.enter_only_load_mode()
    assert sent_commands == []
    assert power_supply.mode == "AC"  # FUNCTION, the AC/DC output mode, is unchanged
