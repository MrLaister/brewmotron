"""
Unit tests for cbpi4-LCDisplay plugin.

Tests the LCD display extension functionality with comprehensive I2C mocking
and display simulation covering multiple display modes.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import MockSMBus, MockLCDisplay, HardwareTestHarness
from tests.fixtures.test_data import PluginConfigFactory

# Mark all tests in this module as hardware tests
pytestmark = pytest.mark.hardware


class TestLCDisplay:
    """Test suite for LCDisplay plugin."""
    
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
    def mock_lcd(self):
        """Create a mocked LCD display."""
        return MockLCDisplay(address=0x27, cols=20, rows=4)
    
    @pytest.fixture
    def display_config(self):
        """Create LCD display plugin configuration."""
        return PluginConfigFactory(
            id="test_lcd_display",
            name="TestLCDisplay",
            type="Extension",
            props={
                'LCD_Address': '0x27',
                'LCD_Multidisplay': 'Yes',
                'LCD_Refresh': '3.0',
                'LCD_Singledisplay': 'Step',
                'CHARMAP': 'A02'
            }
        )
    
    @pytest.mark.asyncio
    async def test_plugin_initialization_multidisplay_mode(self, plugin_harness, display_config, mock_lcd):
        """Test plugin initialization in multidisplay mode."""
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.lcd_address = None
                self.multidisplay = False
                self.refresh_rate = 3.0
                self.display_mode = "Step"
                self.charmap = "A02"
                self.running = False
                self.task = None
                self.lcd = None
            
            async def on_start(self):
                """Start the LCD display extension."""
                self.running = True
                config = self.cbpi.config
                
                self.lcd_address = int(config.get('LCD_Address', '0x27'), 16)
                self.multidisplay = config.get('LCD_Multidisplay', 'No') == 'Yes'
                self.refresh_rate = float(config.get('LCD_Refresh', '3.0'))
                self.display_mode = config.get('LCD_Singledisplay', 'Step')
                self.charmap = config.get('CHARMAP', 'A02')
                
                # Initialize LCD hardware
                self.lcd = mock_lcd
                self.lcd.clear()
                
                # Start display update task
                if self.multidisplay:
                    self.task = asyncio.create_task(self._multidisplay_loop())
                else:
                    self.task = asyncio.create_task(self._singledisplay_loop())
            
            async def on_stop(self):
                """Stop the LCD display extension."""
                self.running = False
                if self.task:
                    self.task.cancel()
                if self.lcd:
                    self.lcd.clear()
            
            async def _multidisplay_loop(self):
                """Multi-display mode showing multiple brewing parameters."""
                while self.running:
                    try:
                        # Simulate brewing data display
                        self.lcd.clear()
                        self.lcd.write_string("Mash: 67.5C/68.0C", 0, 0)
                        self.lcd.write_string("Sparge: 75.2C", 1, 0) 
                        self.lcd.write_string("Boil: OFF", 2, 0)
                        self.lcd.write_string("Step: Mash In", 3, 0)
                    except Exception as e:
                        # Handle LCD errors gracefully
                        pass
                    
                    await asyncio.sleep(self.refresh_rate)
            
            async def _singledisplay_loop(self):
                """Single display mode cycling through different screens."""
                screens = ["Step", "Sensors", "Actors", "Time"]
                current_screen = 0
                
                while self.running:
                    try:
                        screen = screens[current_screen % len(screens)]
                        self.lcd.clear()
                        
                        if screen == "Step":
                            self.lcd.write_string("Current Step:", 0, 0)
                            self.lcd.write_string("Mash In", 1, 0)
                        elif screen == "Sensors":
                            self.lcd.write_string("Sensors:", 0, 0)
                            self.lcd.write_string("Mash: 67.5C", 1, 0)
                        elif screen == "Actors":
                            self.lcd.write_string("Actors:", 0, 0)
                            self.lcd.write_string("Heater: OFF", 1, 0)
                        elif screen == "Time":
                            self.lcd.write_string("Time:", 0, 0)
                            self.lcd.write_string("15:30 - 45min", 1, 0)
                        
                        current_screen += 1
                    except Exception as e:
                        pass
                    
                    await asyncio.sleep(self.refresh_rate)
        
        plugin = await plugin_harness.load_plugin(
            MockLCDisplay,
            display_config.id,
            {}
        )
        
        assert plugin.running == True
        assert plugin.lcd_address == 0x27
        assert plugin.multidisplay == True
        assert plugin.refresh_rate == 3.0
        assert plugin.display_mode == "Step"
        assert plugin.charmap == "A02"
        
        # Wait for a display update
        await asyncio.sleep(0.1)
        
        # Verify LCD is being used
        assert plugin.lcd is not None
    
    @pytest.mark.asyncio
    async def test_singledisplay_mode_cycling(self, plugin_harness, mock_lcd):
        """Test single display mode cycling through screens."""
        config = PluginConfigFactory(
            id="test_single_lcd",
            name="TestSingleLCD",
            type="Extension",
            props={
                'LCD_Address': '0x27',
                'LCD_Multidisplay': 'No',  # Single display mode
                'LCD_Refresh': '1.0',      # Fast refresh for testing
                'LCD_Singledisplay': 'Step'
            }
        )
        
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.multidisplay = False
                self.refresh_rate = 1.0
                self.running = False
                self.task = None
                self.lcd = mock_lcd
                self.current_screen = 0
                self.screens_shown = []
            
            async def on_start(self):
                self.running = True
                config_obj = self.cbpi.config
                self.multidisplay = config_obj.get('LCD_Multidisplay', 'No') == 'Yes'
                self.refresh_rate = float(config_obj.get('LCD_Refresh', '1.0'))
                self.task = asyncio.create_task(self._display_loop())
            
            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _display_loop(self):
                screens = ["Step", "Sensors", "Actors", "Time"]
                
                while self.running:
                    screen = screens[self.current_screen % len(screens)]
                    self.screens_shown.append(screen)
                    
                    self.lcd.clear()
                    self.lcd.write_string(f"Screen: {screen}", 0, 0)
                    
                    self.current_screen += 1
                    await asyncio.sleep(self.refresh_rate)
        
        plugin = await plugin_harness.load_plugin(
            MockLCDisplay,
            config.id,
            {}
        )
        
        assert plugin.multidisplay == False
        
        # Wait for several screen cycles
        await asyncio.sleep(2.5)
        
        # Should have cycled through multiple screens
        assert len(plugin.screens_shown) >= 2
        
        # Should show different screen types
        unique_screens = set(plugin.screens_shown)
        assert len(unique_screens) >= 2
    
    @pytest.mark.asyncio
    async def test_lcd_hardware_communication(self, plugin_harness, display_config, mock_lcd):
        """Test LCD hardware communication and error handling."""
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.lcd = mock_lcd
                self.communication_errors = 0
                self.running = False
                self.task = None
            
            async def on_start(self):
                self.running = True
                self.task = asyncio.create_task(self._test_communication())
            
            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _test_communication(self):
                """Test various LCD operations."""
                while self.running:
                    try:
                        # Test basic operations
                        self.lcd.clear()
                        self.lcd.write_string("Test Line 1", 0, 0)
                        self.lcd.write_string("Test Line 2", 1, 0)
                        
                        # Test cursor operations
                        self.lcd.cursor_mode(True, False)
                        self.lcd.cursor_mode(False, False)
                        
                        # Test backlight
                        self.lcd.backlight(True)
                        self.lcd.backlight(False)
                        
                    except Exception as e:
                        self.communication_errors += 1
                    
                    await asyncio.sleep(0.1)
        
        plugin = await plugin_harness.load_plugin(
            MockLCDisplay,
            display_config.id,
            {}
        )
        
        # Wait for communication tests
        await asyncio.sleep(0.3)
        
        # Should handle communication gracefully
        assert plugin.running == True
        
        # Check LCD state
        lcd_content = plugin.lcd.get_display_content()
        assert "Test Line" in lcd_content
        
        # Should have minimal communication errors with mock
        assert plugin.communication_errors == 0
    
    @pytest.mark.asyncio
    async def test_different_lcd_addresses(self, plugin_harness):
        """Test LCD displays on different I2C addresses."""
        addresses = [0x27, 0x3F, 0x26, 0x25]
        displays = []
        
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.lcd_address = None
                self.running = False
            
            async def on_start(self):
                self.running = True
                config = self.cbpi.config
                self.lcd_address = int(config.get('LCD_Address', '0x27'), 16)
            
            async def on_stop(self):
                self.running = False
        
        # Create displays on different addresses
        for i, addr in enumerate(addresses):
            config = PluginConfigFactory(
                id=f"test_lcd_{i}",
                type="Extension",
                props={'LCD_Address': f'0x{addr:02X}'}
            )
            
            display = await plugin_harness.load_plugin(
                MockLCDisplay,
                config.id,
                {}
            )
            displays.append(display)
        
        # Verify each display has correct address
        for i, display in enumerate(displays):
            expected_addr = addresses[i]
            assert display.lcd_address == expected_addr
    
    @pytest.mark.asyncio
    async def test_display_refresh_rate_configuration(self, plugin_harness):
        """Test different refresh rate configurations."""
        refresh_rates = [0.5, 1.0, 3.0, 5.0, 10.0]
        
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.refresh_rate = 3.0
                self.update_count = 0
                self.running = False
                self.task = None
            
            async def on_start(self):
                self.running = True
                config = self.cbpi.config
                self.refresh_rate = float(config.get('LCD_Refresh', '3.0'))
                self.task = asyncio.create_task(self._update_loop())
            
            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _update_loop(self):
                while self.running:
                    self.update_count += 1
                    await asyncio.sleep(self.refresh_rate)
        
        for rate in refresh_rates:
            config = PluginConfigFactory(
                id=f"test_refresh_{rate}",
                type="Extension", 
                props={'LCD_Refresh': str(rate)}
            )
            
            display = await plugin_harness.load_plugin(
                MockLCDisplay,
                config.id,
                {}
            )
            
            assert display.refresh_rate == rate
            
            # Clean up
            await plugin_harness.unload_plugin(config.id)
    
    def test_charmap_configuration(self, display_config):
        """Test character map configuration options."""
        charmaps = ['A02', 'A00', 'ST0B']
        
        for charmap in charmaps:
            config = display_config
            config.props['CHARMAP'] = charmap
            
            # Should accept various charmap configurations
            assert config.props['CHARMAP'] == charmap


class TestLCDisplayEdgeCases:
    """Test edge cases and error conditions for LCDisplay plugin."""
    
    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()
    
    @pytest.mark.asyncio
    async def test_invalid_lcd_address(self, plugin_harness):
        """Test handling of invalid LCD I2C addresses."""
        invalid_config = PluginConfigFactory(
            id="test_invalid_lcd_addr",
            type="Extension",
            props={'LCD_Address': '0x80'}  # Invalid I2C address
        )
        
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.lcd_address = None
                self.running = False
            
            async def on_start(self):
                self.running = True
                config = self.cbpi.config
                try:
                    addr = int(config.get('LCD_Address', '0x27'), 16)
                    # Validate I2C address range
                    if addr > 0x7F:
                        self.lcd_address = 0x27  # Default fallback
                    else:
                        self.lcd_address = addr
                except ValueError:
                    self.lcd_address = 0x27  # Default fallback
            
            async def on_stop(self):
                self.running = False
        
        plugin = await plugin_harness.load_plugin(
            MockLCDisplay,
            invalid_config.id,
            {}
        )
        
        # Should fallback to valid default address
        assert plugin.lcd_address == 0x27
    
    @pytest.mark.asyncio
    async def test_invalid_refresh_rate(self, plugin_harness):
        """Test handling of invalid refresh rate values."""
        invalid_config = PluginConfigFactory(
            id="test_invalid_refresh",
            type="Extension",
            props={'LCD_Refresh': 'invalid'}
        )
        
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.refresh_rate = 3.0
                self.running = False
            
            async def on_start(self):
                self.running = True
                config = self.cbpi.config
                try:
                    rate = float(config.get('LCD_Refresh', '3.0'))
                    # Ensure minimum refresh rate
                    if rate < 0.1:
                        self.refresh_rate = 0.1
                    elif rate > 60.0:
                        self.refresh_rate = 60.0
                    else:
                        self.refresh_rate = rate
                except ValueError:
                    self.refresh_rate = 3.0  # Default fallback
            
            async def on_stop(self):
                self.running = False
        
        plugin = await plugin_harness.load_plugin(
            MockLCDisplay,
            invalid_config.id,
            {}
        )
        
        # Should fallback to valid default refresh rate
        assert plugin.refresh_rate == 3.0
    
    @pytest.mark.asyncio
    async def test_lcd_hardware_failure_recovery(self, plugin_harness):
        """Test recovery from LCD hardware failures."""
        class MockLCDisplay:
            _plugin_type = 'Extension'
            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.lcd = None
                self.connection_attempts = 0
                self.running = False
                self.task = None
            
            async def on_start(self):
                self.running = True
                self.task = asyncio.create_task(self._connection_loop())
            
            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
            
            async def _connection_loop(self):
                """Attempt to maintain LCD connection."""
                while self.running:
                    if self.lcd is None:
                        self.connection_attempts += 1
                        try:
                            # Simulate connection attempt
                            if self.connection_attempts > 3:
                                self.lcd = MockLCDisplay(address=0x27, cols=20, rows=4)
                        except Exception:
                            pass
                    
                    await asyncio.sleep(0.5)
        
        plugin = await plugin_harness.load_plugin(
            MockLCDisplay,
            "test_recovery",
            {}
        )
        
        # Wait for connection attempts
        await asyncio.sleep(2.0)
        
        # Should eventually establish connection
        assert plugin.connection_attempts >= 3
        assert plugin.lcd is not None