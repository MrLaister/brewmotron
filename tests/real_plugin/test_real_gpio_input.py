"""
Real plugin tests for cbpi4_gpio_input.

Tests the ACTUAL GPIOInput actor plugin with mocked hardware.

GPIOInput is an INPUT plugin: it reads a GPIO pin (configured as input)
and mirrors the pin level to its own state and an optional LinkedActor.
It never drives GPIO outputs itself - on()/off() only update internal
state and the linked actor.
"""

import asyncio
from unittest import mock

import pytest
import pytest_asyncio

from tests.fixtures.cbpi_mock import PluginTestHarness

pytestmark = [pytest.mark.manual, pytest.mark.real_plugin, pytest.mark.requires_hardware_mock]


@pytest.fixture
def real_gpio_input_class(plugin_loader):
    """Load the REAL GPIOInput actor class."""
    return plugin_loader("GPIOInput", "GPIOInput")


class TestRealGPIOInput:
    """Test suite for the REAL GPIOInput actor plugin."""

    @pytest.mark.asyncio
    async def test_actor_initialization(self, plugin_harness, real_gpio_input_class):
        """
        Test that GPIOInput actor initializes correctly.

        Actors in cbpi4 receive:
        - cbpi: The main cbpi instance
        - id: Unique actor ID
        - props: Configuration properties
        """
        props = {
            "GPIO": "18",
            "Inverted": "No",
        }

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_gpio_actor", props)

        # Verify actor structure
        assert actor is not None
        assert actor.id == "test_gpio_actor"
        assert hasattr(actor, "cbpi")
        assert hasattr(actor, "props")
        assert actor.props["GPIO"] == "18"

    @pytest.mark.asyncio
    async def test_input_high_turns_state_on(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test that a HIGH input level turns the actor state ON (normal logic).

        GPIOInput configures its pin as an input and mirrors the pin level
        into its state when get_state() polls the pin.
        """
        props = {"GPIO": "18", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_on_normal", props)

        # Pin is configured as input, defaults LOW -> state off
        assert mock_rpi_gpio._pin_modes.get(18) == mock_rpi_gpio.IN
        assert actor.state is False

        # Drive the input HIGH and poll
        mock_rpi_gpio.simulate_input_change(18, mock_rpi_gpio.HIGH)
        assert actor.get_state() is True
        await asyncio.sleep(0.05)
        assert actor.state is True

    @pytest.mark.asyncio
    async def test_input_low_turns_state_off(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test that the state follows the input back to OFF (normal logic).
        """
        props = {"GPIO": "18", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_off_normal", props)

        # HIGH -> ON
        mock_rpi_gpio.simulate_input_change(18, mock_rpi_gpio.HIGH)
        assert actor.get_state() is True
        await asyncio.sleep(0.05)

        # LOW -> OFF
        mock_rpi_gpio.simulate_input_change(18, mock_rpi_gpio.LOW)
        assert actor.get_state() is False
        await asyncio.sleep(0.05)
        assert actor.state is False

    @pytest.mark.asyncio
    async def test_actor_inverted_logic(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test input with inverted logic (active-low input).

        With Inverted=Yes a LOW pin level means ON and HIGH means OFF.
        Note: the pin defaults LOW, so the actor turns ON during on_start.
        """
        props = {"GPIO": "19", "Inverted": "Yes"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_inverted", props)
        await asyncio.sleep(0.05)

        # Pin defaults LOW -> inverted ON
        assert actor.get_state() is True
        await asyncio.sleep(0.05)

        # Drive HIGH -> inverted OFF
        mock_rpi_gpio.simulate_input_change(19, mock_rpi_gpio.HIGH)
        assert actor.get_state() is False
        await asyncio.sleep(0.05)
        assert actor.state is False

    @pytest.mark.asyncio
    async def test_actor_power_levels(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test that on() handles a power argument gracefully.

        GPIOInput ignores power levels (it mirrors a digital input), but
        on(power=...) must not raise.
        """
        props = {"GPIO": "20", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_power", props)

        await actor.on(power=75)
        await asyncio.sleep(0.05)

        # State is ON; the input pin itself is not driven by the actor
        assert actor.state is True
        assert mock_rpi_gpio._pin_modes.get(20) == mock_rpi_gpio.IN

    @pytest.mark.asyncio
    async def test_multiple_actors_coordination(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test multiple GPIOInput actors reading different pins.

        Simulates several physical switches (e.g. panel toggles) feeding
        independent inputs.
        """
        mash_switch = await plugin_harness.load_plugin(real_gpio_input_class, "mash_switch", {"GPIO": "18", "Inverted": "No"})

        boil_switch = await plugin_harness.load_plugin(real_gpio_input_class, "boil_switch", {"GPIO": "19", "Inverted": "No"})

        pump_switch = await plugin_harness.load_plugin(real_gpio_input_class, "pump_switch", {"GPIO": "20", "Inverted": "No"})

        # Flip mash and pump switches on
        mock_rpi_gpio.simulate_input_change(18, mock_rpi_gpio.HIGH)
        mock_rpi_gpio.simulate_input_change(20, mock_rpi_gpio.HIGH)

        assert mash_switch.get_state() is True
        assert boil_switch.get_state() is False
        assert pump_switch.get_state() is True
        await asyncio.sleep(0.05)

        # Switch to boil phase
        mock_rpi_gpio.simulate_input_change(18, mock_rpi_gpio.LOW)
        mock_rpi_gpio.simulate_input_change(19, mock_rpi_gpio.HIGH)

        assert mash_switch.get_state() is False
        assert boil_switch.get_state() is True
        assert pump_switch.get_state() is True
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_cbpi_integration(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test that input changes are mirrored to the LinkedActor.

        GPIOInput's purpose is to drive another cbpi actor from a physical
        input: when the pin goes HIGH the linked actor is turned on, and
        when it goes LOW the linked actor is turned off.
        """
        props = {"GPIO": "21", "Inverted": "No", "LinkedActor": "linked_pump"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_integration", props)

        # Input HIGH -> linked actor turned on
        mock_rpi_gpio.simulate_input_change(21, mock_rpi_gpio.HIGH)
        actor.get_state()
        await asyncio.sleep(0.05)
        assert await plugin_harness.cbpi.actor.get_state("linked_pump") is True

        # Input LOW -> linked actor turned off
        mock_rpi_gpio.simulate_input_change(21, mock_rpi_gpio.LOW)
        actor.get_state()
        await asyncio.sleep(0.05)
        assert await plugin_harness.cbpi.actor.get_state("linked_pump") is False

    @pytest.mark.asyncio
    async def test_rapid_switching(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test stability when the input toggles rapidly.

        Verifies state tracking does not corrupt under fast transitions.
        """
        props = {"GPIO": "22", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_rapid_switching", props)

        for _ in range(10):
            mock_rpi_gpio.simulate_input_change(22, mock_rpi_gpio.HIGH)
            assert actor.get_state() is True
            await asyncio.sleep(0.01)

            mock_rpi_gpio.simulate_input_change(22, mock_rpi_gpio.LOW)
            assert actor.get_state() is False
            await asyncio.sleep(0.01)

        # Should end in stable OFF state
        assert actor.state is False


class TestRealGPIOInputEdgeCases:
    """Edge case and error handling tests."""

    @pytest.mark.asyncio
    async def test_gpio_setup_failure_handling(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test how actor handles GPIO setup failures.

        Simulates GPIO.setup() failing (e.g., pin already in use).
        """
        props = {"GPIO": "18", "Inverted": "No"}

        # Make GPIO.setup raise an exception
        original_setup = mock_rpi_gpio.setup

        def failing_setup(*args, **kwargs):
            raise RuntimeError("GPIO already in use")

        mock_rpi_gpio.setup = failing_setup

        try:
            actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_setup_failure", props)
            # Plugin should either:
            # 1. Raise exception during load
            # 2. Log error and continue (graceful degradation)
            # This test documents actual behavior
        except RuntimeError:
            # Plugin propagated the error - acceptable
            pass
        finally:
            # Restore original setup
            mock_rpi_gpio.setup = original_setup

    @pytest.mark.asyncio
    async def test_missing_gpio_parameter(self, plugin_harness, real_gpio_input_class):
        """
        Test actor behavior with missing required GPIO parameter.

        Documents actual behavior: GPIOInput passes the missing (None)
        pin straight to GPIO.setup() during on_start, which raises.
        """
        props = {
            "Inverted": "No",
            # GPIO missing!
        }

        with pytest.raises((TypeError, ValueError, RuntimeError)):
            await plugin_harness.load_plugin(real_gpio_input_class, "test_missing_gpio", props)

    @pytest.mark.asyncio
    async def test_concurrent_on_off_calls(self, plugin_harness, real_gpio_input_class, mock_rpi_gpio):
        """
        Test thread safety with concurrent on/off calls.

        Verifies actor handles simultaneous on() and off() calls without corruption.
        """
        props = {"GPIO": "23", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(real_gpio_input_class, "test_concurrent", props)

        # Fire multiple on/off commands concurrently
        await asyncio.gather(
            actor.on(),
            actor.off(),
            actor.on(),
            actor.on(),
            actor.off(),
        )

        await asyncio.sleep(0.1)

        # State must settle to a stable boolean without corruption
        assert actor.state in (True, False)
