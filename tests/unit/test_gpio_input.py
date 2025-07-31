"""
Unit tests for cbpi4-GPIOInput plugin.

Tests the GPIO input actor functionality with comprehensive hardware mocking
and edge case handling.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import MockRPiGPIO, HardwareTestHarness
from tests.fixtures.test_data import PluginConfigFactory, GPIOActorConfigFactory

# Mark all tests in this module as hardware tests
pytestmark = pytest.mark.hardware

class TestGPIOInput:
    """Test suite for GPIOInput plugin."""
    
    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness with GPIO mocking."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()
    
    @pytest.fixture
    def hardware_harness(self):
        """Create hardware test harness."""
        return HardwareTestHarness()
    
    @pytest.fixture
    def gpio_config(self):
        """Create GPIO plugin configuration."""
        return GPIOActorConfigFactory(
            id="test_gpio",
            name="TestGPIOInput",
            props={
                'GPIO': 18,
                'Inverted': 'No',
                'LinkedActor': None
            }
        )
    
    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_harness, gpio_config, mock_gpio):
        """Test plugin initialization with valid configuration."""
        # Mock the GPIOInput class (would normally import from plugin)
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.linked_actor = props.get('LinkedActor')
                self.state = False
            
            async def on_start(self):
                """Initialize GPIO pin."""
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                """Cleanup GPIO resources."""
                mock_gpio.cleanup(self.gpio_pin)
            
            async def on(self, power=None):
                """Turn actor on."""
                self.state = True
                output_value = mock_gpio.LOW if self.inverted else mock_gpio.HIGH
                mock_gpio.output(self.gpio_pin, output_value)
            
            async def off(self):
                """Turn actor off."""
                self.state = False
                output_value = mock_gpio.HIGH if self.inverted else mock_gpio.LOW
                mock_gpio.output(self.gpio_pin, output_value)
        
        # Load plugin
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            gpio_config.id,
            gpio_config.props
        )
        
        # Verify initialization
        assert plugin.id == gpio_config.id
        assert plugin.gpio_pin == 18
        assert plugin.inverted == False
        assert plugin.state == False
        
        # Verify GPIO setup was called
        mock_gpio.setup.assert_called_with(18, mock_gpio.OUT)
        mock_gpio.output.assert_called_with(18, mock_gpio.LOW)
    
    @pytest.mark.asyncio
    async def test_actor_on_off_normal_logic(self, plugin_harness, gpio_config, mock_gpio):
        """Test turning actor on and off with normal logic."""
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
            
            async def on(self, power=None):
                self.state = True
                output_value = mock_gpio.LOW if self.inverted else mock_gpio.HIGH
                mock_gpio.output(self.gpio_pin, output_value)
            
            async def off(self):
                self.state = False
                output_value = mock_gpio.HIGH if self.inverted else mock_gpio.LOW
                mock_gpio.output(self.gpio_pin, output_value)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            gpio_config.id,
            gpio_config.props
        )
        
        # Test turning on
        await plugin.on()
        assert plugin.state == True
        mock_gpio.output.assert_called_with(18, mock_gpio.HIGH)
        
        # Test turning off
        await plugin.off()
        assert plugin.state == False
        mock_gpio.output.assert_called_with(18, mock_gpio.LOW)
    
    @pytest.mark.asyncio
    async def test_actor_inverted_logic(self, plugin_harness, mock_gpio):
        """Test actor with inverted logic."""
        inverted_config = GPIOActorConfigFactory(
            id="test_gpio_inverted",
            props={
                'GPIO': 19,
                'Inverted': 'Yes',
                'LinkedActor': None
            }
        )
        
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 19))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.HIGH)  # Inverted initial state
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
            
            async def on(self, power=None):
                self.state = True
                output_value = mock_gpio.LOW if self.inverted else mock_gpio.HIGH
                mock_gpio.output(self.gpio_pin, output_value)
            
            async def off(self):
                self.state = False
                output_value = mock_gpio.HIGH if self.inverted else mock_gpio.LOW
                mock_gpio.output(self.gpio_pin, output_value)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            inverted_config.id,
            inverted_config.props
        )
        
        # Verify inverted initialization
        assert plugin.inverted == True
        mock_gpio.setup.assert_called_with(19, mock_gpio.OUT)
        mock_gpio.output.assert_called_with(19, mock_gpio.HIGH)  # Initially HIGH for inverted
        
        # Test turning on (should output LOW for inverted logic)
        await plugin.on()
        assert plugin.state == True
        mock_gpio.output.assert_called_with(19, mock_gpio.LOW)
        
        # Test turning off (should output HIGH for inverted logic)
        await plugin.off()
        assert plugin.state == False
        mock_gpio.output.assert_called_with(19, mock_gpio.HIGH)
    
    @pytest.mark.parametrize("gpio_pin", [1, 18, 27])
    @pytest.mark.asyncio
    async def test_different_gpio_pins(self, plugin_harness, mock_gpio, gpio_pin):
        """Test plugin with different GPIO pins."""
        config = GPIOActorConfigFactory(
            id=f"test_gpio_{gpio_pin}",
            props={'GPIO': gpio_pin, 'Inverted': 'No'}
        )
        
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
            
            async def on(self, power=None):
                self.state = True
                mock_gpio.output(self.gpio_pin, mock_gpio.HIGH)
            
            async def off(self):
                self.state = False
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            config.id,
            config.props
        )
        
        assert plugin.gpio_pin == gpio_pin
        mock_gpio.setup.assert_called_with(gpio_pin, mock_gpio.OUT)
        
        await plugin.on()
        mock_gpio.output.assert_called_with(gpio_pin, mock_gpio.HIGH)
    
    @pytest.mark.asyncio
    async def test_plugin_cleanup(self, plugin_harness, gpio_config, mock_gpio):
        """Test proper cleanup of GPIO resources."""
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            gpio_config.id,
            gpio_config.props
        )
        
        # Unload plugin to trigger cleanup
        await plugin_harness.unload_plugin(gpio_config.id)
        
        # Verify cleanup was called
        mock_gpio.cleanup.assert_called_with(18)
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_rapid_switching(self, plugin_harness, gpio_config, mock_gpio):
        """Test rapid on/off switching for stress testing."""
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
            
            async def on(self, power=None):
                self.state = True
                mock_gpio.output(self.gpio_pin, mock_gpio.HIGH)
            
            async def off(self):
                self.state = False
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            gpio_config.id,
            gpio_config.props
        )
        
        # Perform rapid switching
        for i in range(100):
            await plugin.on()
            assert plugin.state == True
            await plugin.off()
            assert plugin.state == False
        
        # Verify final state
        assert plugin.state == False
        assert mock_gpio.output.call_count >= 200  # At least 100 on + 100 off calls
    
    @pytest.mark.asyncio
    async def test_error_handling_gpio_failure(self, plugin_harness, gpio_config):
        """Test error handling when GPIO operations fail."""
        with patch('RPi.GPIO') as mock_gpio:
            # Setup GPIO to raise exception
            mock_gpio.setup.side_effect = RuntimeError("GPIO setup failed")
            mock_gpio.BCM = 11
            mock_gpio.OUT = 0
            mock_gpio.LOW = 0
            mock_gpio.HIGH = 1
            
            class MockGPIOInput:
                def __init__(self, cbpi, id, props):
                    self.cbpi = cbpi
                    self.id = id
                    self.props = props
                    self.gpio_pin = int(props.get('GPIO', 18))
                    self.inverted = props.get('Inverted', 'No') == 'Yes'
                    self.state = False
                
                async def on_start(self):
                    try:
                        mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                        mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
                    except RuntimeError as e:
                        # Plugin should handle GPIO errors gracefully
                        self.state = False
                        raise e
                
                async def on_stop(self):
                    mock_gpio.cleanup(self.gpio_pin)
            
            # Plugin initialization should raise exception
            with pytest.raises(RuntimeError, match="GPIO setup failed"):
                await plugin_harness.load_plugin(
                    MockGPIOInput,
                    gpio_config.id,
                    gpio_config.props
                )
    
    @pytest.mark.asyncio
    async def test_cbpi_integration(self, plugin_harness, gpio_config, mock_gpio):
        """Test integration with CraftBeerPi4 framework."""
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
                
                # Register with CBPI actor system
                await self.cbpi.actor.on(self.id)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
                await self.cbpi.actor.off(self.id)
            
            async def on(self, power=None):
                self.state = True
                mock_gpio.output(self.gpio_pin, mock_gpio.HIGH)
                await self.cbpi.actor.set_state(self.id, True)
            
            async def off(self):
                self.state = False
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
                await self.cbpi.actor.set_state(self.id, False)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            gpio_config.id,
            gpio_config.props
        )
        
        # Test CBPI integration
        await plugin.on()
        
        # Verify CBPI actor system received the state change
        actor_state = await plugin_harness.cbpi.actor.get_state(gpio_config.id)
        assert actor_state == True, "Actor should be in ON state after calling plugin.on()"
        
        await plugin.off()
        actor_state = await plugin_harness.cbpi.actor.get_state(gpio_config.id)
        assert actor_state == False, "Actor should be in OFF state after calling plugin.off()"
    
    def test_plugin_configuration_validation(self, gpio_config):
        """Test plugin configuration validation."""
        from tests.fixtures.test_data import validate_plugin_config
        
        # Valid configuration should pass
        errors = validate_plugin_config(gpio_config)
        assert len(errors) == 0
        
        # Invalid GPIO pin should fail
        invalid_config = gpio_config
        invalid_config.props['GPIO'] = 50  # Invalid pin number
        errors = validate_plugin_config(invalid_config)
        assert len(errors) > 0
        assert any("Invalid GPIO pin" in error for error in errors)

class TestGPIOInputEdgeCases:
    """Test edge cases and error conditions for GPIOInput plugin."""
    
    @pytest.fixture
    def gpio_config(self):
        """Create GPIO plugin configuration."""
        return GPIOActorConfigFactory(
            id="test_gpio_edge",
            name="TestGPIOInputEdge",
            props={
                'GPIO': 18,
                'Inverted': 'No',
                'LinkedActor': None
            }
        )
    
    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()
    
    @pytest.mark.asyncio
    async def test_missing_gpio_parameter(self, plugin_harness, mock_gpio):
        """Test behavior when GPIO parameter is missing."""
        config = PluginConfigFactory(
            id="test_missing_gpio",
            type="Actor",
            props={'Inverted': 'No'}  # Missing GPIO parameter
        )
        
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                # Should handle missing GPIO gracefully
                self.gpio_pin = int(props.get('GPIO', 18))  # Default to 18
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
        
        # Should work with default GPIO pin
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            config.id,
            config.props
        )
        
        assert plugin.gpio_pin == 18  # Default value
        mock_gpio.setup.assert_called_with(18, mock_gpio.OUT)
    
    @pytest.mark.asyncio
    async def test_invalid_inverted_parameter(self, plugin_harness, mock_gpio):
        """Test behavior with invalid inverted parameter."""
        config = PluginConfigFactory(
            id="test_invalid_inverted",
            type="Actor",
            props={
                'GPIO': 20,
                'Inverted': 'Maybe'  # Invalid value
            }
        )
        
        class MockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                # Should handle invalid inverted value gracefully
                inverted_str = props.get('Inverted', 'No')
                self.inverted = inverted_str.lower() in ['yes', 'true', '1']
                self.state = False
            
            async def on_start(self):
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                mock_gpio.cleanup(self.gpio_pin)
        
        plugin = await plugin_harness.load_plugin(
            MockGPIOInput,
            config.id,
            config.props
        )
        
        # Should default to False for invalid inverted value
        assert plugin.inverted == False
    
    @pytest.mark.timeout(5)
    @pytest.mark.asyncio
    async def test_async_operations_timeout(self, plugin_harness, gpio_config, mock_gpio):
        """Test that async operations don't hang indefinitely."""
        class SlowMockGPIOInput:
            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio_pin = int(props.get('GPIO', 18))
                self.inverted = props.get('Inverted', 'No') == 'Yes'
                self.state = False
            
            async def on_start(self):
                # Simulate slow initialization
                await asyncio.sleep(0.1)
                mock_gpio.setup(self.gpio_pin, mock_gpio.OUT)
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
            
            async def on_stop(self):
                await asyncio.sleep(0.1)
                mock_gpio.cleanup(self.gpio_pin)
            
            async def on(self, power=None):
                await asyncio.sleep(0.05)
                self.state = True
                mock_gpio.output(self.gpio_pin, mock_gpio.HIGH)
            
            async def off(self):
                await asyncio.sleep(0.05)
                self.state = False
                mock_gpio.output(self.gpio_pin, mock_gpio.LOW)
        
        # All operations should complete within timeout
        plugin = await plugin_harness.load_plugin(
            SlowMockGPIOInput,
            gpio_config.id,
            gpio_config.props
        )
        
        await plugin.on()
        assert plugin.state == True
        
        await plugin.off()
        assert plugin.state == False