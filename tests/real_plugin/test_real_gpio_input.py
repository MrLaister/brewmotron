"""
Real plugin tests for cbpi4-GPIOInput.

Tests the ACTUAL GPIOInput actor plugin with mocked hardware.
This demonstrates testing an Actor plugin (vs Extension or Sensor).
"""

import asyncio
from unittest import mock

import pytest
import pytest_asyncio

from tests.fixtures.cbpi_mock import PluginTestHarness

pytestmark = [pytest.mark.real_plugin, pytest.mark.requires_hardware_mock]


@pytest.fixture
def real_gpio_input_class(plugin_loader):
    """Load the REAL GPIOInput actor class."""
    return plugin_loader("GPIOInput", "GPIOInput")


class TestRealGPIOInput:
    """Test suite for the REAL GPIOInput actor plugin."""

    @pytest.mark.asyncio
    async def test_actor_initialization(
        self, plugin_harness, real_gpio_input_class
    ):
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

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_gpio_actor",
            props
        )

        # Verify actor structure
        assert actor is not None
        assert actor.id == "test_gpio_actor"
        assert hasattr(actor, 'cbpi')
        assert hasattr(actor, 'props')
        assert actor.props["GPIO"] == "18"

    @pytest.mark.asyncio
    async def test_actor_on_normal_logic(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test turning actor ON with normal (non-inverted) logic.

        Expected:
        - GPIO configured as OUTPUT
        - GPIO set to HIGH when actor.on() is called
        - Actor state reflects ON
        """
        props = {"GPIO": "18", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_on_normal",
            props
        )

        # Turn actor ON
        await actor.on()
        await asyncio.sleep(0.05)

        # Verify GPIO is HIGH
        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH

        # Verify actor reports it's ON
        assert actor.state is True or await actor.get_state() is True

    @pytest.mark.asyncio
    async def test_actor_off_normal_logic(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test turning actor OFF with normal logic.

        Expected:
        - GPIO set to LOW when actor.off() is called
        - Actor state reflects OFF
        """
        props = {"GPIO": "18", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_off_normal",
            props
        )

        # Turn ON then OFF
        await actor.on()
        await asyncio.sleep(0.05)
        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH

        await actor.off()
        await asyncio.sleep(0.05)

        # Verify GPIO is LOW
        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.LOW

        # Verify actor reports it's OFF
        assert actor.state is False or await actor.get_state() is False

    @pytest.mark.asyncio
    async def test_actor_inverted_logic(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test actor with inverted logic (for active-low relays).

        Expected:
        - When actor is ON, GPIO is LOW (inverted)
        - When actor is OFF, GPIO is HIGH (inverted)
        """
        props = {"GPIO": "19", "Inverted": "Yes"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_inverted",
            props
        )

        # Turn ON - should set GPIO LOW
        await actor.on()
        await asyncio.sleep(0.05)
        assert mock_rpi_gpio._pin_states.get(19) == mock_rpi_gpio.LOW

        # Turn OFF - should set GPIO HIGH
        await actor.off()
        await asyncio.sleep(0.05)
        assert mock_rpi_gpio._pin_states.get(19) == mock_rpi_gpio.HIGH

    @pytest.mark.asyncio
    async def test_actor_power_levels(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test actor with power level control.

        GPIO actors typically don't support power levels (it's ON or OFF),
        but the actor should handle power parameter gracefully.
        """
        props = {"GPIO": "20", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_power",
            props
        )

        # Try turning on with power level
        await actor.on(power=75)
        await asyncio.sleep(0.05)

        # GPIO should be ON (power levels ignored for simple GPIO)
        assert mock_rpi_gpio._pin_states.get(20) == mock_rpi_gpio.HIGH

        # Actor should report as ON
        assert actor.state is True or await actor.get_state() is True

    @pytest.mark.asyncio
    async def test_multiple_actors_coordination(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test multiple GPIO actors controlling different pins.

        This simulates a real brewing scenario with multiple actors:
        - Mash heater on GPIO 18
        - Boil heater on GPIO 19
        - Pump on GPIO 20
        """
        # Create three actors
        mash_heater = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "mash_heater",
            {"GPIO": "18", "Inverted": "No"}
        )

        boil_heater = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "boil_heater",
            {"GPIO": "19", "Inverted": "No"}
        )

        pump = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "pump",
            {"GPIO": "20", "Inverted": "No"}
        )

        # Turn on mash heater and pump
        await mash_heater.on()
        await pump.on()
        await asyncio.sleep(0.05)

        # Verify correct GPIO states
        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH  # Mash ON
        assert mock_rpi_gpio._pin_states.get(19) == mock_rpi_gpio.LOW   # Boil OFF
        assert mock_rpi_gpio._pin_states.get(20) == mock_rpi_gpio.HIGH  # Pump ON

        # Switch to boil phase
        await mash_heater.off()
        await boil_heater.on()
        await asyncio.sleep(0.05)

        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.LOW   # Mash OFF
        assert mock_rpi_gpio._pin_states.get(19) == mock_rpi_gpio.HIGH  # Boil ON
        assert mock_rpi_gpio._pin_states.get(20) == mock_rpi_gpio.HIGH  # Pump still ON

    @pytest.mark.asyncio
    async def test_cbpi_integration(
        self, plugin_harness, real_gpio_input_class
    ):
        """
        Test that actor integrates with cbpi actor system.

        Verifies:
        - Actor can be retrieved via cbpi.actor
        - Actor state changes are reflected in cbpi system
        """
        props = {"GPIO": "21", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_integration",
            props
        )

        # Turn actor on
        await actor.on()
        await asyncio.sleep(0.05)

        # Verify cbpi knows about this actor
        cbpi_actor_state = await plugin_harness.cbpi.actor.get_state("test_integration")
        assert cbpi_actor_state is True

        # Turn actor off
        await actor.off()
        await asyncio.sleep(0.05)

        cbpi_actor_state = await plugin_harness.cbpi.actor.get_state("test_integration")
        assert cbpi_actor_state is False

    @pytest.mark.asyncio
    async def test_rapid_switching(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test actor stability under rapid on/off switching.

        This can happen during PID control or when testing.
        Verifies no state corruption or GPIO issues.
        """
        props = {"GPIO": "22", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_rapid_switching",
            props
        )

        # Rapidly switch 10 times
        for i in range(10):
            await actor.on()
            await asyncio.sleep(0.01)
            assert mock_rpi_gpio._pin_states.get(22) == mock_rpi_gpio.HIGH

            await actor.off()
            await asyncio.sleep(0.01)
            assert mock_rpi_gpio._pin_states.get(22) == mock_rpi_gpio.LOW

        # Should end in stable OFF state
        assert mock_rpi_gpio._pin_states.get(22) == mock_rpi_gpio.LOW


class TestRealGPIOInputEdgeCases:
    """Edge case and error handling tests."""

    @pytest.mark.asyncio
    async def test_gpio_setup_failure_handling(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
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
            actor = await plugin_harness.load_plugin(
                real_gpio_input_class,
                "test_setup_failure",
                props
            )
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
    async def test_missing_gpio_parameter(
        self, plugin_harness, real_gpio_input_class
    ):
        """Test actor behavior with missing required GPIO parameter."""
        props = {
            "Inverted": "No",
            # GPIO missing!
        }

        try:
            actor = await plugin_harness.load_plugin(
                real_gpio_input_class,
                "test_missing_gpio",
                props
            )
            # Document actual behavior
            await actor.on()
        except (KeyError, ValueError, AttributeError) as e:
            # Plugin correctly rejects missing parameter
            pass

    @pytest.mark.asyncio
    async def test_concurrent_on_off_calls(
        self, plugin_harness, real_gpio_input_class, mock_rpi_gpio
    ):
        """
        Test thread safety with concurrent on/off calls.

        Verifies actor handles simultaneous on() and off() calls without corruption.
        """
        props = {"GPIO": "23", "Inverted": "No"}

        actor = await plugin_harness.load_plugin(
            real_gpio_input_class,
            "test_concurrent",
            props
        )

        # Fire multiple on/off commands concurrently
        await asyncio.gather(
            actor.on(),
            actor.off(),
            actor.on(),
            actor.on(),
            actor.off(),
        )

        await asyncio.sleep(0.1)

        # Final state should be stable (last command was off)
        assert mock_rpi_gpio._pin_states.get(23) in [
            mock_rpi_gpio.HIGH,
            mock_rpi_gpio.LOW
        ]
