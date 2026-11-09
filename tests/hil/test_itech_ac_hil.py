"""Hardware-in-the-loop tests for the IT7900EP driver. They never turn the output on."""
import pytest

from drivers.iTechAC.itech_ac import ITechACPowerSupply
from tests.hil.conftest import require_output_off


def error_queue(instrument):
    return instrument.query("SYSTEM:ERROR?").strip()


def test_identifies_as_an_it7900ep(it7900ep):
    assert it7900ep.connected
    assert ITechACPowerSupply.is_supported(it7900ep.id)
    assert it7900ep.load_only is True


def test_load_only_blocks_turning_the_output_on(it7900ep):
    with pytest.raises(ValueError, match="load_only"):
        it7900ep.output_state = True

    # The blocked setting must not reach the instrument
    assert it7900ep.query("OUTPUT?").strip() == "0"
    assert it7900ep.output_state is False


def test_turning_the_output_off_is_allowed(it7900ep):
    it7900ep.output_state = False

    assert it7900ep.query("OUTPUT?").strip() == "0"
    assert it7900ep.output_state is False
    assert error_queue(it7900ep).startswith("0,")


def test_voltage_setpoint_reads_as_numbers(it7900ep):
    # Read-only: queries SOURCE:VOLTAGE? and changes nothing
    voltage = it7900ep.voltage
    if it7900ep.phase_mode == "THREE":
        assert type(voltage) is tuple and len(voltage) == 3
        assert all(type(volts) is float for volts in voltage)
    else:
        assert type(voltage) is float
    assert error_queue(it7900ep).startswith("0,")


def test_mode_toggles_and_reads_back(it7900ep):
    original_mode = it7900ep.mode
    # Three-phase mode allows only AC and ACDC; single-phase also allows DC
    if it7900ep.phase_mode == "THREE":
        other_mode = "ACDC" if original_mode == "AC" else "AC"
    else:
        other_mode = "DC" if original_mode == "AC" else "AC"

    for target in (other_mode, original_mode):
        require_output_off(it7900ep)
        it7900ep.mode = target
        assert it7900ep.query("FUNCTION?").strip() == target
        assert it7900ep.mode == target
        assert error_queue(it7900ep).startswith("0,")

    require_output_off(it7900ep)
