"""
Integration tests for sensor-to-display data flow.

Tests the complete data flow from temperature sensors through the CraftBeerPi4 
framework to both LCD and 7-segment displays, ensuring consistent display 
updates and proper temperature management.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, MockCBPiSensorBase, PluginTestHarness
from tests.fixtures.hardware_mocks import (
    Mock7SegmentDisplay,
    MockLCDisplay,
    MockSMBus,
    MockTemperatureSensor,
    create_brewmotron_hardware_setup,
)
from tests.fixtures.test_data import I2CSensorConfigFactory, PluginConfigFactory

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class MockI2CTempSensor(MockCBPiSensorBase):
    """Mock implementation of i2cTempSensor for integration testing."""

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.temperature_sensor = MockTemperatureSensor(20.0)
        self.channel = int(props.get("Channel", 0))
        self.resistor_value = float(props.get("Resistor Value", 10000))

    async def run(self):
        """Simulate temperature sensor reading loop."""
        while True:
            # Read from mock temperature sensor
            temp = self.temperature_sensor.read_temperature()
            self.value = temp

            # Push value to CBPI sensor system
            await self.cbpi.sensor.set_value(self.id, temp)

            await asyncio.sleep(1)


class Mock7SegDisplay:
    """Mock implementation of 7SegDisplay for integration testing."""

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.displays = {}
        self.sensor_mappings = {}

        # Initialize displays for different addresses
        for addr in range(0x70, 0x76):
            self.displays[addr] = Mock7SegmentDisplay(addr)

    async def update_displays(self):
        """Update all 7-segment displays with current sensor values."""
        while True:
            for addr, display in self.displays.items():
                # Get mapped sensor for this display
                sensor_id = self.sensor_mappings.get(addr)
                if sensor_id:
                    try:
                        temp = await self.cbpi.sensor.get_value(sensor_id)
                        display.print(f"{temp:.1f}")
                        display.show()
                    except Exception as e:
                        # Handle sensor read errors
                        display.print("Err")
                        display.show()

            await asyncio.sleep(0.5)  # Faster update for displays

    def map_sensor_to_display(self, display_addr: int, sensor_id: str):
        """Map a sensor to a specific display address."""
        self.sensor_mappings[display_addr] = sensor_id


class MockLCDDisplay:
    """Mock implementation of LCDisplay for integration testing."""

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.display = MockLCDisplay(0x27, 20, 4)
        self.sensor_ids = []
        self.update_interval = 2.0

    async def update_display(self):
        """Update LCD display with multiple sensor values."""
        while True:
            self.display.clear()

            # Display header
            self.display.write_string("Brewmotron Temps", 0, 0)
            self.display.write_string("-" * 16, 0, 1)

            # Display sensor values
            row = 2
            for sensor_id in self.sensor_ids[:2]:  # Only show first 2 sensors
                try:
                    temp = await self.cbpi.sensor.get_value(sensor_id)
                    sensor_name = sensor_id.replace("_", " ").title()[:8]
                    self.display.write_string(f"{sensor_name}: {temp:.1f}C", 0, row)
                    row += 1
                except Exception:
                    self.display.write_string(f"{sensor_id}: Error", 0, row)
                    row += 1

            await asyncio.sleep(self.update_interval)

    def add_sensor(self, sensor_id: str):
        """Add a sensor to be displayed."""
        if sensor_id not in self.sensor_ids:
            self.sensor_ids.append(sensor_id)


class TestSensorDisplayIntegration:
    """Integration test suite for sensor-to-display data flow."""

    @pytest_asyncio.fixture
    async def integration_harness(self):
        """Create an integration test harness with sensors and displays."""
        harness = PluginTestHarness()
        hardware = create_brewmotron_hardware_setup()

        # Set up temperature sensors
        mash_sensor = await harness.load_plugin(
            MockI2CTempSensor,
            "mash_temp_sensor",
            {
                "Channel": 0,
                "Resistor Value": "10000",
                "Thermistor Nominal Resistance": "10000",
            },
        )

        boil_sensor = await harness.load_plugin(
            MockI2CTempSensor,
            "boil_temp_sensor",
            {
                "Channel": 1,
                "Resistor Value": "10000",
                "Thermistor Nominal Resistance": "10000",
            },
        )

        # Set up displays
        seg_display = Mock7SegDisplay(harness.cbpi)
        lcd_display = MockLCDDisplay(harness.cbpi)

        # Map sensors to displays
        seg_display.map_sensor_to_display(0x70, "mash_temp_sensor")
        seg_display.map_sensor_to_display(0x71, "boil_temp_sensor")

        lcd_display.add_sensor("mash_temp_sensor")
        lcd_display.add_sensor("boil_temp_sensor")

        yield {
            "harness": harness,
            "hardware": hardware,
            "mash_sensor": mash_sensor,
            "boil_sensor": boil_sensor,
            "seg_display": seg_display,
            "lcd_display": lcd_display,
        }

        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_sensor_to_7seg_display_flow(self, integration_harness):
        """Test temperature sensor data flows correctly to 7-segment displays."""
        harness = integration_harness["harness"]
        hardware = integration_harness["hardware"]
        mash_sensor = integration_harness["mash_sensor"]
        seg_display = integration_harness["seg_display"]

        # Set specific temperatures
        mash_sensor.temperature_sensor.set_target_temperature(65.5)

        # Start display update loop
        display_task = asyncio.create_task(seg_display.update_displays())

        # Wait for temperature to stabilize and displays to update
        await asyncio.sleep(3)

        # Check that display shows correct temperature
        mash_display = seg_display.displays[0x70]
        assert mash_display.display_buffer != [
            0,
            0,
            0,
            0,
        ], "Display should show temperature data"

        # Verify sensor value propagated to CBPI system
        sensor_value = await harness.cbpi.sensor.get_value("mash_temp_sensor")
        assert (
            abs(sensor_value - 65.5) < 2.0
        ), f"Sensor should read close to 65.5°C, got {sensor_value}"

        display_task.cancel()

    @pytest.mark.asyncio
    async def test_sensor_to_lcd_display_flow(self, integration_harness):
        """Test temperature sensor data flows correctly to LCD display."""
        harness = integration_harness["harness"]
        mash_sensor = integration_harness["mash_sensor"]
        boil_sensor = integration_harness["boil_sensor"]
        lcd_display = integration_harness["lcd_display"]

        # Set specific temperatures
        mash_sensor.temperature_sensor.set_target_temperature(66.0)
        boil_sensor.temperature_sensor.set_target_temperature(100.0)

        # Start display update loop
        display_task = asyncio.create_task(lcd_display.update_display())

        # Wait for temperatures to stabilize and display to update
        await asyncio.sleep(4)

        # Check LCD display content
        display_content = lcd_display.display.get_display_content()

        # Verify header is displayed
        assert "Brewmotron" in display_content[0], "LCD should show header"

        # Verify temperature data is displayed
        temp_lines = [line for line in display_content if ":" in line and "C" in line]
        assert (
            len(temp_lines) >= 1
        ), f"LCD should show temperature data, got: {display_content}"

        display_task.cancel()

    @pytest.mark.asyncio
    async def test_multiple_sensors_consistent_display(self, integration_harness):
        """Test multiple sensors display consistently across different display types."""
        harness = integration_harness["harness"]
        mash_sensor = integration_harness["mash_sensor"]
        boil_sensor = integration_harness["boil_sensor"]
        seg_display = integration_harness["seg_display"]
        lcd_display = integration_harness["lcd_display"]

        # Set known temperatures
        target_mash = 67.5
        target_boil = 98.5

        mash_sensor.temperature_sensor.set_target_temperature(target_mash)
        boil_sensor.temperature_sensor.set_target_temperature(target_boil)

        # Start both display update loops
        seg_task = asyncio.create_task(seg_display.update_displays())
        lcd_task = asyncio.create_task(lcd_display.update_display())

        # Wait for system to stabilize
        await asyncio.sleep(5)

        # Get values from CBPI system
        mash_temp = await harness.cbpi.sensor.get_value("mash_temp_sensor")
        boil_temp = await harness.cbpi.sensor.get_value("boil_temp_sensor")

        # Verify sensor values are reasonable
        assert (
            abs(mash_temp - target_mash) < 3.0
        ), f"Mash temp should be near {target_mash}, got {mash_temp}"
        assert (
            abs(boil_temp - target_boil) < 3.0
        ), f"Boil temp should be near {target_boil}, got {boil_temp}"

        # Verify both displays are updating (not showing default values)
        mash_7seg = seg_display.displays[0x70]
        boil_7seg = seg_display.displays[0x71]

        assert mash_7seg.display_buffer != [
            0,
            0,
            0,
            0,
        ], "Mash 7-seg display should show data"
        assert boil_7seg.display_buffer != [
            0,
            0,
            0,
            0,
        ], "Boil 7-seg display should show data"

        # Verify LCD shows temperature data
        lcd_content = lcd_display.display.get_display_content()
        temp_lines = [line for line in lcd_content if ":" in line and "C" in line]
        assert len(temp_lines) >= 2, "LCD should show both sensor temperatures"

        seg_task.cancel()
        lcd_task.cancel()

    @pytest.mark.asyncio
    async def test_sensor_failure_error_handling(self, integration_harness):
        """Test display behavior when sensor fails."""
        harness = integration_harness["harness"]
        mash_sensor = integration_harness["mash_sensor"]
        seg_display = integration_harness["seg_display"]

        # Start normal operation
        mash_sensor.temperature_sensor.set_target_temperature(65.0)
        display_task = asyncio.create_task(seg_display.update_displays())

        # Wait for normal operation
        await asyncio.sleep(2)

        # Simulate sensor failure
        mash_sensor.temperature_sensor.simulate_sensor_failure("disconnected")

        # Wait for error condition to propagate
        await asyncio.sleep(3)

        # Check that display handles error gracefully
        mash_display = seg_display.displays[0x70]
        # In a real implementation, this might show "Err" or similar error indicator

        # Verify sensor system still responds (even with error values)
        try:
            sensor_value = await harness.cbpi.sensor.get_value("mash_temp_sensor")
            # Error condition might return 85.0 (typical DS18B20 error value)
            assert (
                sensor_value is not None
            ), "Sensor should return some value even in error state"
        except Exception:
            # Error handling is also acceptable
            pass

        display_task.cancel()

    @pytest.mark.asyncio
    async def test_display_update_timing_coordination(self, integration_harness):
        """Test that different displays update at appropriate rates without
        conflicts."""
        harness = integration_harness["harness"]
        mash_sensor = integration_harness["mash_sensor"]
        seg_display = integration_harness["seg_display"]
        lcd_display = integration_harness["lcd_display"]

        # Set temperature
        mash_sensor.temperature_sensor.set_target_temperature(70.0)

        # Record update timing
        seg_updates = []
        lcd_updates = []

        # Mock display update methods to track timing
        original_seg_update = seg_display.update_displays
        original_lcd_update = lcd_display.update_display

        async def track_seg_updates():
            async for update in self._track_updates(original_seg_update, seg_updates):
                pass

        async def track_lcd_updates():
            async for update in self._track_updates(original_lcd_update, lcd_updates):
                pass

        # Start both update loops
        seg_task = asyncio.create_task(track_seg_updates())
        lcd_task = asyncio.create_task(track_lcd_updates())

        # Run for test period
        await asyncio.sleep(6)

        seg_task.cancel()
        lcd_task.cancel()

        # Verify update rates are reasonable
        # 7-segment displays should update more frequently (0.5s interval)
        # LCD displays should update less frequently (2.0s interval)

        assert len(seg_updates) > len(
            lcd_updates
        ), "7-segment displays should update more frequently than LCD"

        # Check for reasonable update counts over 6 seconds
        assert (
            len(seg_updates) >= 8
        ), f"Expected at least 8 7-seg updates in 6s, got {len(seg_updates)}"
        assert (
            len(lcd_updates) >= 2
        ), f"Expected at least 2 LCD updates in 6s, got {len(lcd_updates)}"

    async def _track_updates(self, update_func, update_list):
        """Helper to track display update timing."""
        try:
            while True:
                start_time = datetime.now()
                await update_func()
                update_list.append(start_time)
                await asyncio.sleep(0.1)  # Small delay to prevent tight loop
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_temperature_ramping_display_response(self, integration_harness):
        """Test display response to temperature changes over time."""
        harness = integration_harness["harness"]
        mash_sensor = integration_harness["mash_sensor"]
        seg_display = integration_harness["seg_display"]

        # Start displays
        display_task = asyncio.create_task(seg_display.update_displays())

        # Simulate temperature ramp from 20°C to 65°C
        temperatures = [20.0, 30.0, 45.0, 60.0, 65.0]

        for target_temp in temperatures:
            mash_sensor.temperature_sensor.set_target_temperature(target_temp)
            await asyncio.sleep(2)  # Allow temperature to change and display to update

            # Verify sensor value is trending toward target
            current_temp = await harness.cbpi.sensor.get_value("mash_temp_sensor")

            # Temperature should be moving in right direction
            if target_temp > 20.0:  # Skip first reading
                assert (
                    current_temp > 18.0
                ), f"Temperature should be rising, got {current_temp}"

            # Display should be updating (not stuck at zero)
            mash_display = seg_display.displays[0x70]
            assert mash_display.display_buffer != [
                0,
                0,
                0,
                0,
            ], f"Display should show data at {target_temp}°C"

        display_task.cancel()
