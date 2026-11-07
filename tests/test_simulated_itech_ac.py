from pathlib import Path

import pytest

from drivers.iTechAC.iTechAC import iTechACPowerSupply

SIMULATION_FILE = Path(__file__).resolve().parents[1] / "drivers" / "iTechAC" / "simulation.yaml"
SIMULATED_BACKEND = f"{SIMULATION_FILE}@sim"
SIMULATED_RESOURCE = "TCPIP0::192.168.1.100::5025::SOCKET"


@pytest.fixture
def power_supply():
    instrument = iTechACPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND)
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
