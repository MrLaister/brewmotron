"""
Real plugin tests for cbpi4-YOUR_PLUGIN_NAME.

TODO: Replace YOUR_PLUGIN_NAME with actual plugin name
TODO: Replace YourPluginClass with actual class name
TODO: Update plugin_type ("Actor", "Sensor", or "Extension")
TODO: Add plugin-specific tests

Tests the ACTUAL production plugin code with mocked hardware.
"""

import asyncio
from unittest import mock

import pytest
import pytest_asyncio

from tests.fixtures.cbpi_mock import PluginTestHarness

# Mark all tests in this module
pytestmark = [pytest.mark.real_plugin, pytest.mark.requires_hardware_mock]


@pytest.fixture
def real_plugin_class(plugin_loader):
    """
    Load the REAL plugin class.

    TODO: Update arguments:
    - First arg: Plugin directory name (e.g., "GPIOInput")
    - Second arg: Class name to import (e.g., "GPIOInput")
    """
    return plugin_loader("YOUR_PLUGIN_NAME", "YourPluginClass")


class TestRealYourPlugin:
    """
    Test suite for the REAL YourPlugin.

    TODO: Rename class to match your plugin
    """

    @pytest.mark.asyncio
    async def test_plugin_initialization(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test that the real plugin can be loaded and initialized.

        This is a smoke test to ensure basic structure is correct.
        """
        # TODO: Update configuration for your plugin
        props = {
            "ConfigKey1": "value1",
            "ConfigKey2": "value2",
        }

        # For Extensions, use empty props and set config instead:
        # plugin_harness.cbpi.config._config_data.update({
        #     "YourConfigKey": "value",
        # })
        # props = {}

        # Load the REAL plugin (not a mock!)
        plugin = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_plugin",
            props
        )

        # Verify plugin loaded correctly
        assert plugin is not None
        assert hasattr(plugin, 'cbpi')

        # For Actors/Sensors, verify id and props
        # assert hasattr(plugin, 'id')
        # assert plugin.id == "test_plugin"
        # assert plugin.props == props

    @pytest.mark.asyncio
    async def test_configuration_parsing(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test that plugin correctly parses its configuration.

        TODO: Add assertions specific to your plugin's config
        """
        props = {
            # TODO: Add your plugin's configuration
            "ConfigKey": "ConfigValue",
        }

        plugin = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_config",
            props
        )

        # Give plugin time to initialize
        await asyncio.sleep(0.1)

        # TODO: Verify configuration was parsed correctly
        # Example:
        # assert plugin.some_attribute == expected_value

    # =========================================================================
    # TODO: Add plugin-specific tests below
    # =========================================================================

    # For Actor plugins:
    @pytest.mark.asyncio
    async def test_actor_on_off(
        self, plugin_harness, real_plugin_class, mock_rpi_gpio
    ):
        """
        Test actor on/off functionality.

        TODO: Only include this if your plugin is an Actor
        TODO: Delete if not an Actor plugin
        """
        props = {
            "GPIO": "18",
            "Inverted": "No",
        }

        actor = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_actor",
            props
        )

        # Test turning ON
        await actor.on()
        await asyncio.sleep(0.05)

        # TODO: Add assertions for ON state
        # assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH

        # Test turning OFF
        await actor.off()
        await asyncio.sleep(0.05)

        # TODO: Add assertions for OFF state
        # assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.LOW

    # For Sensor plugins:
    @pytest.mark.asyncio
    async def test_sensor_reading(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test sensor value reading.

        TODO: Only include this if your plugin is a Sensor
        TODO: Delete if not a Sensor plugin
        """
        props = {
            # TODO: Add sensor configuration
        }

        sensor = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_sensor",
            props
        )

        # Get sensor value
        value = await sensor.get_value()

        # TODO: Add assertions about sensor value
        # assert isinstance(value, float)
        # assert value >= 0.0

    # For Extension plugins:
    @pytest.mark.asyncio
    async def test_extension_background_task(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test extension background tasks.

        TODO: Only include this if your plugin is an Extension
        TODO: Delete if not an Extension plugin
        """
        # Extensions read from cbpi.config
        plugin_harness.cbpi.config._config_data.update({
            # TODO: Add your extension's configuration
            "YourConfigKey": "value",
        })

        extension = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_extension",
            {}  # Extensions don't use props
        )

        # Let background tasks run
        await asyncio.sleep(1.0)

        # TODO: Add assertions about extension behavior

    @pytest.mark.asyncio
    async def test_plugin_cleanup(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test that plugin properly cleans up on stop.

        TODO: Add cleanup verification specific to your plugin
        """
        props = {
            # TODO: Add configuration
        }

        plugin = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_cleanup",
            props
        )

        await asyncio.sleep(0.1)

        # Stop the plugin
        if hasattr(plugin, 'on_stop'):
            await plugin.on_stop()

        # TODO: Verify cleanup
        # - Background tasks cancelled?
        # - GPIO set to safe state?
        # - Resources released?


class TestRealYourPluginEdgeCases:
    """
    Edge case and error handling tests.

    TODO: Rename class to match your plugin
    TODO: Add edge cases specific to your plugin
    """

    @pytest.mark.asyncio
    async def test_missing_required_config(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test behavior when required configuration is missing.

        TODO: Update to test your plugin's required config
        """
        props = {
            # Missing required config!
        }

        try:
            plugin = await plugin_harness.load_plugin(
                real_plugin_class,
                "test_missing_config",
                props
            )
            # If it loads, check how it handles missing config
            await asyncio.sleep(0.1)
        except (KeyError, ValueError, AttributeError) as e:
            # Plugin correctly rejects missing config
            pass

    @pytest.mark.asyncio
    async def test_invalid_config_values(
        self, plugin_harness, real_plugin_class
    ):
        """
        Test handling of invalid configuration values.

        TODO: Add test cases for invalid config specific to your plugin
        """
        props = {
            # TODO: Add invalid configuration values
            "SomeKey": "invalid_value",
        }

        try:
            plugin = await plugin_harness.load_plugin(
                real_plugin_class,
                "test_invalid_config",
                props
            )
            # Document actual behavior
            await asyncio.sleep(0.1)
        except (ValueError, TypeError) as e:
            # Plugin rejected invalid config
            pass


# =============================================================================
# COPY-PASTE TEMPLATES FOR COMMON TEST PATTERNS
# =============================================================================

# TEMPLATE: GPIO Output Test
"""
@pytest.mark.asyncio
async def test_gpio_output(plugin_harness, real_plugin_class, mock_rpi_gpio):
    props = {"GPIO": "18", "Inverted": "No"}

    plugin = await plugin_harness.load_plugin(
        real_plugin_class,
        "test_gpio",
        props
    )

    await plugin.on()  # Or whatever triggers GPIO
    await asyncio.sleep(0.05)

    # Verify GPIO state
    assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH
"""

# TEMPLATE: I2C Communication Test
"""
@pytest.mark.asyncio
async def test_i2c_communication(
    plugin_harness,
    real_plugin_class,
    mock_i2c_devices
):
    plugin_harness.cbpi.config._config_data.update({
        "I2CAddress": "0x70",
    })

    plugin = await plugin_harness.load_plugin(
        real_plugin_class,
        "test_i2c",
        {}
    )

    await asyncio.sleep(0.5)

    # Verify I2C device interaction
    display = mock_i2c_devices[0x70]
    # Check display state...
"""

# TEMPLATE: Sensor Value Test
"""
@pytest.mark.asyncio
async def test_sensor_values(plugin_harness, real_plugin_class):
    # Register sensors
    plugin_harness.cbpi.sensor.register_sensor(
        "test_sensor",
        {"id": "test_sensor", "name": "Test Sensor"}
    )

    # Set sensor value
    await plugin_harness.cbpi.sensor.set_value("test_sensor", 65.5)

    # Get sensor value
    value = await plugin_harness.cbpi.sensor.get_value("test_sensor")
    assert value == 65.5
"""

# TEMPLATE: Multiple Instances Test
"""
@pytest.mark.asyncio
async def test_multiple_instances(plugin_harness, real_plugin_class):
    # Load first instance
    plugin1 = await plugin_harness.load_plugin(
        real_plugin_class,
        "instance_1",
        {"GPIO": "18"}
    )

    # Load second instance
    plugin2 = await plugin_harness.load_plugin(
        real_plugin_class,
        "instance_2",
        {"GPIO": "19"}
    )

    # Test both work independently
    await plugin1.on()
    await plugin2.on()
    # Add assertions...
"""

# TEMPLATE: Error Handling Test
"""
@pytest.mark.asyncio
async def test_hardware_error_handling(
    plugin_harness,
    real_plugin_class,
    mock_rpi_gpio
):
    # Make hardware operation fail
    def failing_operation(*args, **kwargs):
        raise RuntimeError("Hardware error")

    mock_rpi_gpio.output = failing_operation

    props = {"GPIO": "18"}

    try:
        plugin = await plugin_harness.load_plugin(
            real_plugin_class,
            "test_error",
            props
        )
        await plugin.on()
        # Check how plugin handles error
    except RuntimeError:
        # Plugin propagated error
        pass
"""
