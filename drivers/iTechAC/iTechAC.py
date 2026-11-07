import os
import sys

# Make the repo root importable, regardless of the working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from drivers.iTech.iTech import iTechPowerSupply


class iTechACPowerSupply(iTechPowerSupply):
    VALID_MODES = ("AC", "DC")

    @property
    def mode(self):
        """Queries the output mode ('AC' or 'DC')."""
        # TODO: MODE is a dummy SCPI command; replace it with the real one
        return self.query("MODE?")

    @mode.setter
    def mode(self, mode_str):
        """Sets the output mode ('AC' or 'DC')."""
        if mode_str not in self.VALID_MODES:
            raise ValueError(f"mode must be one of {self.VALID_MODES}, got {mode_str!r}")
        self.write(f"MODE {mode_str}")


if __name__ == "__main__":
    # Locate the simulation file next to this script, regardless of the working directory
    sim_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation.yaml")
    SIMULATED_BACKEND = f"{sim_file}@sim"
    SIMULATED_RESOURCE = "TCPIP0::192.168.1.100::5025::SOCKET"

    print(f"Initializing virtual interface for: {SIMULATED_RESOURCE}...")
    power_supply = iTechACPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND)

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

        print("\nAll simulated instrument checks passed.")

    finally:
        power_supply.disconnect()
        print("\nVirtual resource channel safely released.")
