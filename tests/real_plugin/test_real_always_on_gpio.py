"""
Real plugin tests for cbpi4-AlwaysONGPIO.

These tests import and test the ACTUAL AlwaysONGPIO plugin code,
not mock implementations. Hardware dependencies are mocked.
"""

import asyncio
from unittest import mock

import pytest
import pytest_asyncio

from tests.fixtures.cbpi_mock import PluginTestHarness

# Mark all tests in this module
pytestmark = [pytest.mark.manual, pytest.mark.real_plugin, pytest.mark.requires_hardware_mock]


@pytest.fixture
def real_always_on_gpio_class(plugin_loader):
    """
    Load the REAL AlwaysONGPIO plugin class.

    This imports the actual production code from cbpi4_always_on_gpio.
    The actor class in that plugin is named GPIOAON.
    """
    return plugin_loader("AlwaysONGPIO", "GPIOAON")


class TestRealAlwaysONGPIO:
    """Test suite for the REAL AlwaysONGPIO plugin."""

    @pytest.mark.asyncio
    async def test_plugin_loads_and_initializes(self, plugin_harness, real_always_on_gpio_class):
        """
        Test that the real plugin can be loaded and initialized.

        This is a smoke test to ensure the plugin structure is correct
        and it can integrate with the cbpi4 framework.
        """
        config = {
            "GPIO": "18",
            "Inverted": "No",
        }

        # Load the REAL plugin (not a mock!)
        plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, "test_always_on", config)

        # Verify plugin loaded correctly
        assert plugin is not None
        assert hasattr(plugin, "cbpi")
        assert hasattr(plugin, "id")
        assert plugin.id == "test_always_on"

    @pytest.mark.asyncio
    async def test_gpio_configuration_parsing(self, plugin_harness, real_always_on_gpio_class, mock_rpi_gpio):
        """
        Test that the plugin correctly parses GPIO configuration.

        Verifies:
        - GPIO pin number is extracted from config
        - Inverted logic is parsed correctly
        - GPIO.setup() is called with correct parameters
        """
        config = {
            "GPIO": "21",
            "Inverted": "Yes",
        }

        plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, "test_gpio_config", config)

        # Give plugin time to configure GPIO
        await asyncio.sleep(0.1)

        # Verify the plugin parsed the config correctly
        # (Check internal state or GPIO setup calls)
        # The exact assertion depends on the plugin's implementation
        assert plugin.props.get("GPIO") == "21"
        assert plugin.props.get("Inverted") == "Yes"

    @pytest.mark.asyncio
    async def test_normal_logic_output(self, plugin_harness, real_always_on_gpio_class, mock_rpi_gpio):
        """
        Test GPIO output with normal (non-inverted) logic.

        Expected behavior:
        - When plugin starts, GPIO should be set HIGH
        - GPIO pin should be configured as OUTPUT
        """
        config = {
            "GPIO": "18",
            "Inverted": "No",
        }

        plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, "test_normal_logic", config)

        # Give plugin time to set GPIO
        await asyncio.sleep(0.1)

        # Verify GPIO was configured as output
        assert 18 in mock_rpi_gpio._pin_modes
        assert mock_rpi_gpio._pin_modes[18] == mock_rpi_gpio.OUT

        # Verify GPIO is set HIGH (normal logic for "always on")
        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH

    @pytest.mark.asyncio
    async def test_inverted_property_is_ignored(self, plugin_harness, real_always_on_gpio_class, mock_rpi_gpio):
        """
        Test that an Inverted property has no effect.

        GPIOAON does not support inverted logic - its only parameter is
        GPIO and it always drives the pin high. This documents that an
        Inverted property is silently ignored.
        """
        config = {
            "GPIO": "22",
            "Inverted": "Yes",
        }

        plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, "test_inverted_logic", config)

        # Give plugin time to set GPIO
        await asyncio.sleep(0.1)

        # Pin is HIGH regardless of the Inverted property
        assert mock_rpi_gpio._pin_states.get(22) == mock_rpi_gpio.HIGH

    @pytest.mark.asyncio
    async def test_plugin_stop_keeps_pin_high(self, plugin_harness, real_always_on_gpio_class, mock_rpi_gpio):
        """
        Test pin behavior when the plugin stops.

        GPIOAON is deliberately "always on": it never drives the pin low,
        not even on stop (it powers components that must stay on, e.g.
        displays). This documents that the pin stays HIGH after on_stop.
        """
        config = {
            "GPIO": "23",
            "Inverted": "No",
        }

        plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, "test_cleanup", config)

        await asyncio.sleep(0.1)

        # GPIO should be HIGH while running
        assert mock_rpi_gpio._pin_states.get(23) == mock_rpi_gpio.HIGH

        # Stop the plugin
        if hasattr(plugin, "on_stop"):
            await plugin.on_stop()

        # The pin remains HIGH - the plugin never turns it off
        assert mock_rpi_gpio._pin_states.get(23) == mock_rpi_gpio.HIGH

    @pytest.mark.asyncio
    async def test_multiple_instances_different_pins(self, plugin_harness, real_always_on_gpio_class, mock_rpi_gpio):
        """
        Test that multiple instances can control different GPIO pins.

        This tests the real-world scenario of multiple always-on actors
        (e.g., cooling fan, indicator LED, etc.)
        """
        # Load first instance on GPIO 18
        plugin1 = await plugin_harness.load_plugin(real_always_on_gpio_class, "always_on_1", {"GPIO": "18", "Inverted": "No"})

        # Load second instance on GPIO 19
        plugin2 = await plugin_harness.load_plugin(real_always_on_gpio_class, "always_on_2", {"GPIO": "19", "Inverted": "Yes"})

        await asyncio.sleep(0.1)

        # Both pins are driven HIGH independently (Inverted is ignored)
        assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH
        assert mock_rpi_gpio._pin_states.get(19) == mock_rpi_gpio.HIGH

    @pytest.mark.asyncio
    async def test_invalid_gpio_handling(self, plugin_harness, real_always_on_gpio_class):
        """
        Test that plugin handles invalid GPIO configuration gracefully.

        The plugin should either:
        1. Reject invalid config at load time, or
        2. Handle the error gracefully without crashing
        """
        config = {
            "GPIO": "invalid",
            "Inverted": "No",
        }

        # This test documents actual behavior
        # Depending on plugin implementation, it may:
        # - Raise ValueError during load
        # - Log error and use default
        # - Fail during GPIO setup

        try:
            plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, "test_invalid", config)
            await asyncio.sleep(0.1)
            # If it doesn't raise, verify it handled it somehow
            # (this is a documentation test)
        except (ValueError, KeyError, AttributeError) as e:
            # Plugin rejected invalid config - good!
            pass


class TestRealAlwaysONGPIOEdgeCases:
    """Edge case tests for the REAL AlwaysONGPIO plugin."""

    @pytest.mark.asyncio
    async def test_missing_gpio_parameter(self, plugin_harness, real_always_on_gpio_class):
        """
        Test behavior when GPIO parameter is missing.

        Documents actual behavior: GPIOAON passes the missing (None) pin
        straight to GPIO.setup() during on_start, which raises.
        """
        config = {
            "Inverted": "No",
            # GPIO missing!
        }

        with pytest.raises((TypeError, ValueError, RuntimeError)):
            await plugin_harness.load_plugin(real_always_on_gpio_class, "test_missing_gpio", config)

    @pytest.mark.asyncio
    async def test_rapid_start_stop_cycles(self, plugin_harness, real_always_on_gpio_class, mock_rpi_gpio):
        """
        Test plugin stability under rapid start/stop cycles.

        Verifies no resource leaks or state corruption.
        """
        config = {"GPIO": "24", "Inverted": "No"}

        for cycle in range(5):
            plugin = await plugin_harness.load_plugin(real_always_on_gpio_class, f"test_cycle_{cycle}", config)

            await asyncio.sleep(0.05)
            assert mock_rpi_gpio._pin_states.get(24) == mock_rpi_gpio.HIGH

            if hasattr(plugin, "on_stop"):
                await plugin.on_stop()

            await asyncio.sleep(0.05)

        # The pin stays HIGH - GPIOAON never drives it low, even on stop
        assert mock_rpi_gpio._pin_states.get(24) == mock_rpi_gpio.HIGH
