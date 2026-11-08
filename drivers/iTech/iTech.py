import os
import easy_scpi as scpi

class ITechPowerSupply(scpi.Instrument):
    """
    Power supply driver intended specifically for high-current power supplies
    """
    def __init__(self, resource_string, backend=""):
        # An empty backend uses real hardware; "<file>.yaml@sim" uses pyvisa-sim
        super().__init__(
            port=resource_string,
            backend=backend,
            port_match=False,  # disabling necessary for pyvisa-sim support
            timeout=5000,
            read_termination='\n',
            write_termination='\n'
        )

    @property
    def voltage(self):
        """Queries the source voltage using easy-scpi property tree mapping."""
        return float(self.source.voltage())

    @voltage.setter
    def voltage(self, volts):
        """Sets the source voltage."""
        self.source.voltage(volts)

    @property
    def output_state(self):
        """Queries whether the output loop is enabled."""
        return self.output()

    @output_state.setter
    def output_state(self, state_str):
        """Sets the output loop (e.g., 'ON' or 'OFF')."""
        self.output(state_str)

    def read_current(self):
        """Fetches dynamic simulated measurement readings."""
        return float(self.measure.current())

if __name__ == "__main__":
    # Locate the simulation file next to this script, regardless of the working directory
    sim_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation.yaml")
    SIMULATED_BACKEND = f"{sim_file}@sim"
    SIMULATED_RESOURCE = "TCPIP0::192.168.1.100::5025::SOCKET"

    print(f"Initializing virtual interface for: {SIMULATED_RESOURCE}...")
    power_supply = ITechPowerSupply(SIMULATED_RESOURCE, backend=SIMULATED_BACKEND)

    try:
        # Open communication channel
        power_supply.connect()

        # Verify baseline communication
        print("\n--- Testing Basic Identification ---")
        identity = power_supply.id
        print(f"Instrument IDN: {identity}")
        assert identity == "Itech Electronics,IT6642C-1200-200,800000000000000001,000.001.038,83.R,13.R"

        print("\n--- Testing Target Setters & Getters ---")
        power_supply.voltage = 12.5
        voltage = power_supply.voltage
        print(f"Configured Voltage level: {voltage} V")
        assert float(voltage) == 12.5

        power_supply.output_state = "ON"
        output_state = power_supply.output_state
        print(f"Current Output Condition: {output_state}")
        assert output_state == "ON"

        print("\n--- Reading Virtual Measurements ---")
        current_reading = power_supply.read_current()
        print(f"Measured Current Draw: {current_reading} A")
        assert float(current_reading) == 1.234

        print("\nAll simulated instrument checks passed.")

    finally:
        power_supply.disconnect()
        print("\nVirtual resource channel safely released.")