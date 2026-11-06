import os
import easy_scpi as scpi

class iTechPowerSupply(scpi.Instrument):
    """
    A custom instrument controller class inheriting from easy-scpi.Instrument.
    This provides explicit high-level Python methods over the dynamic attributes.
    """
    def __init__(self, resource_string, backend=None):
        # Pass the simulation backend down to PyVISA
        super().__init__(resource_string, backend=backend, port_match=False,read_termination="\n",write_termination="\n")  # need port_match=False for pyvisa-sim
        pyvisa_resource = self._Instrument__inst
        pyvisa_resource.read_termination = "\n"
        pyvisa_resource.write_termination = "\n"

    def reset(self):
        """Reset the instrument to default state."""
        self.rst()  # Sends *RST
        
    def get_identity(self):
        """Retrieve instrument signature."""
        return self.idn()  # Sends *IDN?

    def configure_output(self, voltage: float, state: bool):
        """High-level abstraction method to set voltage and turn on output."""
        self.source.voltage = voltage          # Sends SOURCE:VOLTAGE <voltage>
        self.output = "ON" if state else "OFF" # Sends OUTPUT <ON/OFF>

    def read_current(self) -> float:
        """Query the instrument for current measurement."""
        response = self.measure.current()      # Sends MEASURE:CURRENT?
        return float(response)


# ==========================================
# TESTING ENVIRONMENT Execution
# ==========================================
if __name__ == "__main__":
    # 1. Point PyVISA-sim to our mock device configuration file
    # This string syntax tells PyVISA to load the local yaml file as a backend
    sim_backend = "simulation.yaml@sim"
    resource_id = "TCPIP0::192.168.1.100::5025::SOCKET"

    print("--- Initializing Virtual Instrument Connection ---")
    
    # 1. Instantiate our custom controller targeting the virtual backend
    power_supply = iTechPowerSupply(resource_id, backend=sim_backend)
    
    # 2. Directly open the backend via the private resource manager
    rm_instance = power_supply._Instrument__rm
    power_supply._Instrument__inst = rm_instance.open_resource(resource_id)
    
    # 3. Explicitly inject the termination parameters PyVISA-Sim requires
    power_supply._Instrument__inst.read_termination = "\n"
    power_supply._Instrument__inst.write_termination = "\n"
    
    # 4. CRUCIAL: Manually set the connection status flags to True.
    # ❌ DO NOT CALL power_supply.connect()
    power_supply._Instrument__connected = True
    
    # 3. Execute the control sequences safely in software
    print(f"Device Identity: {power_supply.get_identity()}")
    
    print("\nSending Reset...")
    power_supply.reset()
    
    print("\nConfiguring Power Supply Settings...")
    power_supply.configure_output(voltage=5.25, state=True)
    
    # Verify the values were correctly sent and cached by the simulation layer
    print(f"Target Voltage State: {power_supply.source.voltage} V")
    print(f"Output Toggle Status: {power_supply.output}")
    
    print("\nReading Live Telemetry...")
    current_reading = power_supply.read_current()
    print(f"Measured Current Draw: {current_reading} A")
    
    print("\n--- Simulation Test Complete ---")
