"""Shared pytest setup."""
import pytest
from pyvisa.highlevel import VisaLibraryBase
from pyvisa_sim.highlevel import SimVisaLibrary


def _forget_simulators():
    for key in [key for key in VisaLibraryBase._registry if issubclass(key[0], SimVisaLibrary)]:
        del VisaLibraryBase._registry[key]


@pytest.fixture(autouse=True)
def fresh_simulators():
    """Gives each test simulated instruments in their simulation.yaml default state.

    pyvisa caches each VISA library it loads for the life of the process, so without
    this pyvisa-sim would carry one test's settings into the next.
    """
    _forget_simulators()
    yield
    _forget_simulators()
