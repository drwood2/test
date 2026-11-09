"""Hardware-in-the-loop fixtures. These tests talk to a real instrument.

Each instrument's tests are skipped unless its variable names it, for example:

    ITECH_AC_RESOURCE=TCPIP0::192.168.200.115::30000::SOCKET \\
    ITECH_DC_RESOURCE=TCPIP0::192.168.200.101::30000::SOCKET pytest tests/hil -v

ITECH_AC_RESOURCE is an IT7900EP; ITECH_DC_RESOURCE is an IT6600C.
ITECH_VISA_BACKEND picks the VISA library; it defaults to "@py" (PyVISA-py).
"""
import os

import pytest

from drivers.iTech.itech import ITechPowerSupply
from drivers.iTechAC.itech_ac import ITechACPowerSupply

AC_RESOURCE = os.environ.get("ITECH_AC_RESOURCE")
DC_RESOURCE = os.environ.get("ITECH_DC_RESOURCE")
VISA_BACKEND = os.environ.get("ITECH_VISA_BACKEND", "@py")

# IT6600C settings saved before each test and restored after it. CC-priority settings
# are restored first, then FUNCTION, then the CV-priority ones: the instrument rejects
# CV-priority settings in CC priority.
_IT6600C_CC_SETTINGS = ("POWER:LIMIT:NEGATIVE", "CURRENT")
_IT6600C_CV_SETTINGS = ("CURRENT:LIMIT", "CURRENT:LIMIT:NEGATIVE", "POWER:LIMIT", "RESISTANCE")


def drain_errors(instrument):
    """Reads the error queue until it is empty, and returns the errors it held."""
    errors = []
    for _ in range(20):
        error = instrument.query("SYSTEM:ERROR?").strip()
        if error.startswith("0,"):
            break
        errors.append(error)
    return errors


def require_output_off(instrument):
    """Fails the test, after sending OUTPUT 0, if the instrument reports its output on."""
    reply = instrument.query("OUTPUT?").strip()
    if reply != "0":
        instrument.write("OUTPUT 0")
        pytest.fail(f"OUTPUT? replied {reply!r}; sent OUTPUT 0 and stopped")


@pytest.fixture
def it7900ep():
    """A real IT7900EP, connected with load_only=True, whose output must start off.

    Teardown turns the output off and restores the output mode it started in.
    """
    if not AC_RESOURCE:
        pytest.skip("set ITECH_AC_RESOURCE to run hardware-in-the-loop tests")

    instrument = ITechACPowerSupply(AC_RESOURCE, backend=VISA_BACKEND, load_only=True)
    instrument.connect()
    try:
        require_output_off(instrument)
        original_mode = instrument.mode
        yield instrument
    finally:
        try:
            instrument.output_state = False
            if instrument.mode != original_mode:
                instrument.mode = original_mode
        finally:
            instrument.disconnect()


@pytest.fixture
def it6600c():
    """A real IT6600C, connected with load_only=True, with its output turned off first.

    The bench unit's output comes up on, so this turns it off (always allowed) rather than
    failing. Teardown restores every load setting with raw writes, which load_only would
    otherwise block; the output is off, so nothing is energized.
    """
    if not DC_RESOURCE:
        pytest.skip("set ITECH_DC_RESOURCE to run IT6600C hardware-in-the-loop tests")

    instrument = ITechPowerSupply(DC_RESOURCE, backend=VISA_BACKEND, load_only=True)
    instrument.connect()
    try:
        instrument.output_state = False
        require_output_off(instrument)
        drain_errors(instrument)
        priority = instrument.query("FUNCTION?").strip()
        saved = {cmd: instrument.query(f"{cmd}?").strip()
                 for cmd in _IT6600C_CC_SETTINGS + _IT6600C_CV_SETTINGS}
        yield instrument
    finally:
        try:
            instrument.output_state = False
            instrument.write("FUNCTION CURRENT")
            instrument.write("FUNCTION:ILOAD 0")
            for cmd in _IT6600C_CC_SETTINGS:
                instrument.write(f"{cmd} {saved[cmd]}")
            instrument.write(f"FUNCTION {priority}")
            for cmd in _IT6600C_CV_SETTINGS:
                instrument.write(f"{cmd} {saved[cmd]}")
            restored = {cmd: instrument.query(f"{cmd}?").strip() for cmd in saved}
            leftover = drain_errors(instrument)
            assert instrument.query("FUNCTION?").strip() == priority
            assert restored == saved, f"settings not restored: {restored} != {saved}"
            assert not leftover, f"restoring left errors: {leftover}"
        finally:
            instrument.disconnect()
