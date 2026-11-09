"""Test file for iTechAC driver"""
from pathlib import Path

import pytest

from drivers.iTech.itech import ITechPowerSupply

SIMULATED_BACKEND = f"{Path(__file__).with_name('simulation.yaml')}@sim"
SIMULATED_RESOURCE = "TCPIP0::192.168.200.100::30000::SOCKET"


@pytest.fixture
def connect_power_supply():
    """Returns a function that connects a simulated power supply, disconnected after the test."""
    instruments = []

    def connect(**kwargs):
        instrument = ITechPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND, **kwargs)
        instrument.connect()
        instruments.append(instrument)
        return instrument

    yield connect
    for instrument in instruments:
        instrument.disconnect()


def test_load_only_is_on_by_default(connect_power_supply):
    assert connect_power_supply().load_only is True


def test_load_only_blocks_setting_voltage(connect_power_supply):
    power_supply = connect_power_supply(load_only=True)

    with pytest.raises(ValueError, match="load_only"):
        power_supply.voltage = 24.0

    # The blocked setting must not reach the instrument
    assert power_supply.voltage == 0.0


def test_voltage_can_be_set_without_load_only(connect_power_supply):
    power_supply = connect_power_supply(load_only=False)

    power_supply.voltage = 12.5
    assert power_supply.voltage == 12.5


def test_turning_on_load_only_blocks_later_voltage_settings(connect_power_supply):
    power_supply = connect_power_supply(load_only=False)
    power_supply.voltage = 12.5

    power_supply.load_only = True
    with pytest.raises(ValueError, match="load_only"):
        power_supply.voltage = 24.0
    assert power_supply.voltage == 12.5


def test_output_is_off_by_default(connect_power_supply):
    power_supply = connect_power_supply()

    assert power_supply.output() == "0"  # the raw reply, as a real IT6600C sends it
    assert power_supply.output_state is False


@pytest.mark.parametrize("on, off", [(True, False), (1, 0), ("ON", "OFF"), ("on", "off"), ("1", "0")])
def test_output_state_accepts_each_documented_form(connect_power_supply, on, off):
    power_supply = connect_power_supply(load_only=False)

    power_supply.output_state = on
    assert power_supply.output() == "1"
    assert power_supply.output_state is True

    power_supply.output_state = off
    assert power_supply.output() == "0"
    assert power_supply.output_state is False


@pytest.mark.parametrize("state", ["ENABLE", 2, None, ""])
def test_invalid_output_states_are_rejected(connect_power_supply, state):
    power_supply = connect_power_supply()

    with pytest.raises(ValueError, match="output_state"):
        power_supply.output_state = state
    assert power_supply.output_state is False


@pytest.mark.parametrize("on", [True, 1, "ON", "on", "1"])
def test_load_only_blocks_turning_the_output_on(connect_power_supply, on):
    power_supply = connect_power_supply(load_only=True)

    with pytest.raises(ValueError, match="load_only"):
        power_supply.output_state = on

    # The blocked setting must not reach the instrument
    assert power_supply.output() == "0"
    assert power_supply.output_state is False


def test_load_only_still_allows_turning_the_output_off(connect_power_supply):
    power_supply = connect_power_supply(load_only=False)
    power_supply.output_state = True

    power_supply.load_only = True
    power_supply.output_state = False
    assert power_supply.output() == "0"
    assert power_supply.output_state is False


# --- Load simulation ---

def test_load_settings_start_at_documented_defaults(connect_power_supply):
    power_supply = connect_power_supply()

    assert power_supply.priority_mode == "VOLTAGE"
    assert power_supply.only_load_mode is False
    assert power_supply.resistance == 0.0


def test_enter_only_load_mode_with_load_only(connect_power_supply):
    power_supply = connect_power_supply(load_only=True)

    power_supply.enter_only_load_mode()
    assert power_supply.priority_mode == "CURRENT"
    assert power_supply.only_load_mode is True
    assert power_supply.query("FUNCTION:ILOAD?") == "1"  # a 1 or 0 reply, like OUTPUT?


def test_configure_a_cc_and_cw_load_with_load_only(connect_power_supply):
    # As the bench IT6600C accepted: a negative current and, in only-load mode, a negative P-
    power_supply = connect_power_supply(load_only=True)
    power_supply.enter_only_load_mode()

    power_supply.current = -10
    power_supply.power = -3000

    assert power_supply.current == -10.0
    assert power_supply.power == -3000.0


def test_sink_current_limit_in_cv_priority_with_load_only(connect_power_supply):
    power_supply = connect_power_supply(load_only=True)
    assert power_supply.priority_mode == "VOLTAGE"

    power_supply.current_limit_negative = -4
    assert power_supply.current_limit_negative == -4.0


def test_only_load_mode_reads_off_in_cv_priority_without_asking(connect_power_supply):
    power_supply = connect_power_supply(load_only=False)
    power_supply.enter_only_load_mode()
    power_supply.priority_mode = "VOLTAGE"

    # The simulator still holds FUNCTION:ILOAD 1, but CV priority can't be in only-load mode
    assert power_supply.query("FUNCTION:ILOAD?") == "1"
    assert power_supply.only_load_mode is False


@pytest.mark.parametrize("name", [
    "current", "resistance", "power", "current_limit", "current_limit_negative",
    "power_limit", "power_limit_negative",
])
def test_load_settings_read_as_floats(connect_power_supply, name):
    assert type(getattr(connect_power_supply(), name)) is float


def test_load_only_blocks_a_sourcing_current(connect_power_supply):
    power_supply = connect_power_supply(load_only=True)

    with pytest.raises(ValueError, match="load_only"):
        power_supply.current = 5
    assert power_supply.current == 50.0  # unchanged

    power_supply.current = 0  # zero neither sources nor sinks
    assert power_supply.current == 0.0


def test_load_only_blocks_turning_only_load_mode_off(connect_power_supply):
    power_supply = connect_power_supply(load_only=True)
    power_supply.enter_only_load_mode()

    with pytest.raises(ValueError, match="load_only"):
        power_supply.only_load_mode = False
    assert power_supply.only_load_mode is True


def test_without_load_only_the_supply_can_leave_load_mode_and_source(connect_power_supply):
    power_supply = connect_power_supply(load_only=False)
    power_supply.enter_only_load_mode()

    power_supply.only_load_mode = False
    power_supply.current = 5
    assert power_supply.only_load_mode is False
    assert power_supply.current == 5.0


def test_load_only_still_blocks_the_output_in_load_mode(connect_power_supply):
    power_supply = connect_power_supply(load_only=True)
    power_supply.enter_only_load_mode()

    with pytest.raises(ValueError, match="load_only"):
        power_supply.output_state = True
    assert power_supply.output() == "0"


def test_load_measurements(connect_power_supply):
    power_supply = connect_power_supply()

    assert power_supply.read_voltage() == 48.0
    assert power_supply.read_power() == 59.23
    assert power_supply.read_current() == 1.234


@pytest.mark.parametrize("value", ["CV", "LOAD", ""])
def test_invalid_priority_modes_are_rejected(connect_power_supply, value):
    power_supply = connect_power_supply()

    with pytest.raises(ValueError):
        power_supply.priority_mode = value
    assert power_supply.priority_mode == "VOLTAGE"
