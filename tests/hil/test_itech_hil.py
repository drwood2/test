"""Hardware-in-the-loop tests for the IT6600C load commands. They never turn the output on."""
import pytest

from tests.hil.conftest import drain_errors, require_output_off


def test_enter_only_load_mode(it6600c):
    it6600c.enter_only_load_mode()

    assert it6600c.query("FUNCTION?").strip() == "CURR"
    assert it6600c.priority_mode == "CURRENT"
    assert it6600c.only_load_mode is True
    assert drain_errors(it6600c) == []
    require_output_off(it6600c)


def test_only_load_mode_reads_off_in_cv_priority(it6600c):
    # FUNCTION:ILOAD? times out in CV priority, so the driver must not ask
    assert it6600c.priority_mode == "VOLTAGE"
    assert it6600c.only_load_mode is False
    assert drain_errors(it6600c) == []


def test_cc_and_cw_load_settings_read_back(it6600c):
    it6600c.enter_only_load_mode()

    it6600c.current = -1
    it6600c.power = -100

    assert it6600c.current == -1.0
    assert it6600c.power == -100.0
    assert float(it6600c.query("POWER:LIMIT:NEGATIVE?")) == -100.0  # only-load POWER sets P-
    assert drain_errors(it6600c) == []
    require_output_off(it6600c)


def test_sink_current_limit_reads_back_in_cv_priority(it6600c):
    it6600c.current_limit_negative = -4

    assert it6600c.current_limit_negative == -4.0
    assert drain_errors(it6600c) == []
    require_output_off(it6600c)


@pytest.mark.parametrize("name, value", [
    ("current", 1),
    ("output_state", True),
    ("only_load_mode", False),
    ("voltage", 10),
])
def test_load_only_blocks_sourcing_without_sending_anything(it6600c, name, value):
    it6600c.enter_only_load_mode()
    current_before = it6600c.current

    with pytest.raises(ValueError, match="load_only"):
        setattr(it6600c, name, value)

    assert it6600c.query("OUTPUT?").strip() == "0"
    assert it6600c.only_load_mode is True
    assert it6600c.current == current_before
    assert drain_errors(it6600c) == []
