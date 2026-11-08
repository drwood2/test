from pathlib import Path

import pytest

from drivers.iTechAC.iTech_ac import ITechACPowerSupply

SIMULATED_BACKEND = f"{Path(__file__).with_name('simulation.yaml')}@sim"
SIMULATED_RESOURCE = "TCPIP0::192.168.1.100::5025::SOCKET"


@pytest.fixture
def power_supply():
    instrument = ITechACPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND)
    instrument.connect()
    yield instrument
    instrument.disconnect()


def test_enable_ac_mode_then_disable_output(power_supply):
    # Start away from the simulator defaults (AC, OFF) so the checks below prove a change
    power_supply.mode = "DC"
    power_supply.output_state = "ON"
    assert power_supply.mode == "DC"
    assert power_supply.output_state == "ON"

    power_supply.mode = "AC"
    assert power_supply.mode == "AC"

    power_supply.output_state = "OFF"
    assert power_supply.output_state == "OFF"


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


def test_surge_sag_run_commands(power_supply):
    power_supply.start_surge_sag()
    power_supply.force_trigger()
    assert power_supply.surge_sag_state() == "0"
    power_supply.abort_surge_sag()
