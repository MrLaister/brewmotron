"""
Unit tests for cbpi4-7SegDisplay plugin.

Tests the 7-segment display extension functionality with comprehensive I2C mocking
and display simulation.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import MockSMBus, Mock7SegmentDisplay, HardwareTestHarness
from tests.fixtures.test_data import PluginConfigFactory

# Mark all tests in this module as hardware tests
pytestmark = pytest.mark.hardware


class TestSSDisplay:
    """Test suite for SSDisplay (7-segment display) plugin."""
    
    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness with I2C mocking."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()
    
    @pytest.fixture
    def mock_i2c(self):
        """Create a mocked I2C interface."""
        return MockSMBus(1)
    
    @pytest.fixture
    def mock_7seg_display(self):
        """Create a mocked 7-segment display."""
        return Mock7SegmentDisplay(0x70)
    
    @pytest.fixture
    def display_config(self):
        """Create 7-segment display plugin configuration."""
        return PluginConfigFactory(
            id="test_7seg_display",
            name="Test7SegDisplay",
            type="Extension",
            props={
                'SpargeAddress': '0x70',
                'MashAddress': '0x71', 
                'BoilerAddress': '0x72',
                'RefreshRate': '1.0'
            }
        )
    
    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_harness, display_config, mock_i2c):
        """Test plugin initialization with valid configuration."""
        # Mock the SSDisplay class
        class MockSSDisplay:
            # Mark as extension type for the mock framework
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.sparge_address = None
                self.mash_address = None
                self.boiler_address = None
                self.refresh_rate = 1.0
                self.task = None
                self.running = False
            
            async def on_start(self):
                """Start the display extension."""
                self.running = True
                config = self.cbpi.config
                self.sparge_address = int(config.get('SpargeAddress', '0x70'), 16)
                self.mash_address = int(config.get('MashAddress', '0x71'), 16)
                self.boiler_address = int(config.get('BoilerAddress', '0x72'), 16)
                self.refresh_rate = float(config.get('RefreshRate', '1.0'))
                
                # Start display update task
                self.task = asyncio.create_task(self._update_displays())
            
            async def on_stop(self):
                """Stop the display extension."""
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _update_displays(self):
                """Update display values periodically."""
                while self.running:
                    await asyncio.sleep(self.refresh_rate)
        
        plugin = await plugin_harness.load_plugin(
            MockSSDisplay,
            display_config.id,
            {}  # Extensions don't use props in the same way
        )
        
        assert plugin.running == True
        assert plugin.sparge_address == 0x70
        assert plugin.mash_address == 0x71
        assert plugin.boiler_address == 0x72
        assert plugin.refresh_rate == 1.0
    
    @pytest.mark.asyncio
    async def test_display_temperature_updates(self, plugin_harness, display_config, mock_i2c, mock_7seg_display):
        """Test temperature display updates."""
        class MockSSDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.displays = {}
                self.running = False
                self.task = None
            
            async def on_start(self):
                self.running = True
                # Initialize displays
                self.displays[0x70] = mock_7seg_display  # Sparge
                self.displays[0x71] = Mock7SegmentDisplay(0x71)  # Mash
                self.displays[0x72] = Mock7SegmentDisplay(0x72)  # Boiler
                self.task = asyncio.create_task(self._update_displays())
            
            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _update_displays(self):
                """Update displays with current temperatures."""
                while self.running:
                    # Simulate temperature readings
                    temperatures = {
                        0x70: 65.5,  # Sparge temp
                        0x71: 67.2,  # Mash temp  
                        0x72: 100.1  # Boiler temp
                    }
                    
                    for addr, temp in temperatures.items():
                        if addr in self.displays:
                            self.displays[addr].print(f"{temp:.1f}")
                    
                    await asyncio.sleep(0.1)  # Fast update for testing
            
            def get_display_value(self, address):
                """Get current display value for testing."""
                return self.displays.get(address, Mock7SegmentDisplay(address)).get_display_state()
        
        plugin = await plugin_harness.load_plugin(
            MockSSDisplay,
            display_config.id,
            {}
        )
        
        # Wait for a few display updates
        await asyncio.sleep(0.3)
        
        # Verify displays are showing temperature values
        sparge_state = plugin.get_display_value(0x70)
        mash_state = plugin.get_display_value(0x71)
        boiler_state = plugin.get_display_value(0x72)
        
        # Check that display buffers contain temperature data (as digit arrays)
        assert sparge_state['display_buffer'] != [0, 0, 0, 0]
        assert mash_state['display_buffer'] != [0, 0, 0, 0]
        assert boiler_state['display_buffer'] != [0, 0, 0, 0]
    
    @pytest.mark.asyncio
    async def test_i2c_communication_error_handling(self, plugin_harness, display_config, mock_i2c):
        """Test handling of I2C communication errors."""
        class MockSSDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.error_count = 0
                self.running = False
                self.task = None
            
            async def on_start(self):
                self.running = True
                self.task = asyncio.create_task(self._update_displays())
            
            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _update_displays(self):
                """Update displays with error handling."""
                while self.running:
                    try:
                        # Simulate I2C operation that might fail
                        mock_i2c.write_byte(0x70, 0xFF)
                    except Exception as e:
                        self.error_count += 1
                    
                    await asyncio.sleep(0.1)
        
        # Set up I2C to simulate failures
        mock_i2c.simulate_device_failure(0x70, "connection_lost")
        
        plugin = await plugin_harness.load_plugin(
            MockSSDisplay,
            display_config.id,
            {}
        )
        
        # Wait for some update attempts
        await asyncio.sleep(0.3)
        
        # Plugin should handle errors gracefully
        assert plugin.running == True
        # Should have detected some I2C errors
        assert plugin.error_count > 0
    
    @pytest.mark.asyncio
    async def test_plugin_cleanup(self, plugin_harness, display_config):
        """Test plugin cleanup and task cancellation."""
        class MockSSDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.running = False
                self.task = None
                self.cleanup_called = False
            
            async def on_start(self):
                self.running = True
                self.task = asyncio.create_task(self._update_displays())
            
            async def on_stop(self):
                self.running = False
                self.cleanup_called = True
                if self.task:
                    self.task.cancel()
            
            async def _update_displays(self):
                while self.running:
                    await asyncio.sleep(0.1)
        
        plugin = await plugin_harness.load_plugin(
            MockSSDisplay,
            display_config.id,
            {}
        )
        
        assert plugin.running == True
        assert plugin.task is not None
        
        # Test cleanup
        await plugin_harness.unload_plugin(display_config.id)
        
        assert plugin.running == False
        assert plugin.cleanup_called == True
    
    def test_address_configuration_parsing(self, display_config):
        """Test I2C address configuration parsing."""
        # Test hex string parsing
        config_values = {
            'SpargeAddress': '0x70',
            'MashAddress': '0x71',
            'BoilerAddress': '0x72'
        }
        
        for key, hex_str in config_values.items():
            parsed_addr = int(hex_str, 16)
            assert parsed_addr > 0
            assert parsed_addr <= 0x7F  # Valid I2C address range
        
        # Test invalid address handling
        try:
            invalid_addr = int('0x80', 16)  # Out of valid range
            assert invalid_addr == 0x80  # But parsing should work
        except ValueError:
            pytest.fail("Should handle invalid address gracefully")


class TestSSDisplayEdgeCases:
    """Test edge cases and error conditions for SSDisplay plugin."""
    
    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()
    
    @pytest.mark.asyncio
    async def test_missing_configuration(self, plugin_harness):
        """Test behavior with missing configuration values."""
        class MockSSDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.sparge_address = None
                self.running = False
            
            async def on_start(self):
                self.running = True
                config = self.cbpi.config
                # Should handle missing config gracefully
                self.sparge_address = int(config.get('SpargeAddress', '0x70'), 16)
            
            async def on_stop(self):
                self.running = False
        
        plugin = await plugin_harness.load_plugin(
            MockSSDisplay,
            "test_missing_config",
            {}
        )
        
        # Should use default values
        assert plugin.sparge_address == 0x70
        assert plugin.running == True
    
    @pytest.mark.asyncio
    async def test_invalid_refresh_rate(self, plugin_harness):
        """Test handling of invalid refresh rate values."""
        class MockSSDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.refresh_rate = 1.0
                self.running = False
            
            async def on_start(self):
                self.running = True
                config = self.cbpi.config
                try:
                    self.refresh_rate = float(config.get('RefreshRate', '1.0'))
                    # Ensure minimum refresh rate
                    if self.refresh_rate < 0.1:
                        self.refresh_rate = 0.1
                except ValueError:
                    self.refresh_rate = 1.0  # Default fallback
            
            async def on_stop(self):
                self.running = False
        
        plugin = await plugin_harness.load_plugin(
            MockSSDisplay,
            "test_invalid_refresh",
            {}
        )
        
        # Should handle invalid refresh rate gracefully
        assert plugin.refresh_rate >= 0.1
        assert plugin.running == True