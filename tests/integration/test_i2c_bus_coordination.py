"""
Integration tests for I2C bus coordination and resource sharing.

Tests multiple plugins sharing the I2C bus simultaneously, ensuring proper
bus arbitration, error handling, and data integrity across multiple devices.
"""

import asyncio
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import (HardwareTestHarness,
                                           Mock7SegmentDisplay, MockSMBus)
from tests.fixtures.test_data import PluginConfigFactory

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class MockI2CDevice:
    """Base class for I2C device simulation."""

    def __init__(self, address: int, bus: MockSMBus):
        self.address = address
        self.bus = bus
        self.transaction_count = 0
        self.last_access = None
        self.access_history = []

    def _record_access(self, operation: str, data=None):
        """Record I2C access for testing."""
        self.transaction_count += 1
        self.last_access = datetime.now()
        self.access_history.append(
            {
                "timestamp": self.last_access,
                "operation": operation,
                "data": data,
                "thread_id": threading.get_ident(),
            }
        )


class Mock7SegI2CPlugin(MockI2CDevice):
    """Mock 7-segment display plugin with I2C operations."""

    def __init__(self, cbpi, display_id: str, address: int = 0x70):
        self.cbpi = cbpi
        self.display_id = display_id
        self.bus = MockSMBus(1)
        super().__init__(address, self.bus)

        self.display_value = 0.0
        self.brightness = 15
        self.update_interval = 0.5
        self._running = False
        self._task = None

    async def start(self):
        """Start the display update loop."""
        self._running = True

        # Initialize display
        self._initialize_display()

        # Start update loop
        self._task = asyncio.create_task(self._update_loop())

    async def stop(self):
        """Stop the display update loop."""
        self._running = False
        if self._task:
            self._task.cancel()

    def _initialize_display(self):
        """Initialize the display hardware."""
        try:
            # System setup
            self.bus.write_byte(self.address, 0x21)
            self._record_access("system_setup", 0x21)

            # Display setup
            self.bus.write_byte(self.address, 0xEF)
            self._record_access("display_setup", 0xEF)

            # Set brightness
            self.bus.write_byte(self.address, 0xE0 | self.brightness)
            self._record_access("brightness", self.brightness)

        except Exception as e:
            self._record_access("init_error", str(e))

    async def _update_loop(self):
        """Main display update loop."""
        while self._running:
            try:
                await self.update_display()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._record_access("update_error", str(e))
                await asyncio.sleep(1)  # Error recovery delay

    async def update_display(self):
        """Update display with current value."""
        try:
            # Convert value to display format
            display_data = self._format_value(self.display_value)

            # Write to display buffer (simplified)
            for i, digit in enumerate(display_data):
                self.bus.write_byte_data(self.address, i * 2, digit & 0xFF)
                self.bus.write_byte_data(self.address, i * 2 + 1, (digit >> 8) & 0xFF)

            self._record_access("display_update", self.display_value)

        except Exception as e:
            self._record_access("display_error", str(e))

    def _format_value(self, value: float) -> list:
        """Format value for display."""
        # Simplified: return 4 digits
        str_val = f"{value:4.1f}".replace(".", "")
        return [int(c) if c.isdigit() else 0 for c in str_val[:4]]

    def set_value(self, value: float):
        """Set display value."""
        self.display_value = value


class MockTempSensorI2CPlugin(MockI2CDevice):
    """Mock temperature sensor plugin with I2C operations."""

    def __init__(self, cbpi, sensor_id: str, address: int = 0x48, channel: int = 0):
        self.cbpi = cbpi
        self.sensor_id = sensor_id
        self.channel = channel
        self.bus = MockSMBus(1)
        super().__init__(address, self.bus)

        self.temperature = 20.0
        self.read_interval = 1.0
        self._running = False
        self._task = None

    async def start(self):
        """Start the sensor reading loop."""
        self._running = True

        # Initialize sensor
        self._initialize_sensor()

        # Start reading loop
        self._task = asyncio.create_task(self._reading_loop())

    async def stop(self):
        """Stop the sensor reading loop."""
        self._running = False
        if self._task:
            self._task.cancel()

    def _initialize_sensor(self):
        """Initialize the temperature sensor."""
        try:
            # Configure ADC (simplified ADS1115 config)
            config_reg = 0x0583  # Default config
            self.bus.write_word_data(self.address, 0x01, config_reg)
            self._record_access("sensor_init", config_reg)

        except Exception as e:
            self._record_access("init_error", str(e))

    async def _reading_loop(self):
        """Main sensor reading loop."""
        while self._running:
            try:
                await self.read_temperature()
                await asyncio.sleep(self.read_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._record_access("read_error", str(e))
                await asyncio.sleep(2)  # Error recovery delay

    async def read_temperature(self):
        """Read temperature from sensor."""
        try:
            # Start conversion
            config_reg = 0x8583 | (self.channel << 12)
            self.bus.write_word_data(self.address, 0x01, config_reg)

            # Small delay for conversion
            await asyncio.sleep(0.001)

            # Read conversion result
            raw_value = self.bus.read_word_data(self.address, 0x00)

            # Convert to temperature (simplified)
            voltage = (raw_value / 32768.0) * 4.096  # 16-bit, 4.096V ref
            self.temperature = 20.0 + (voltage * 10)  # Simplified conversion

            # Update CBPI sensor system
            await self.cbpi.sensor.set_value(self.sensor_id, self.temperature)

            self._record_access("temperature_read", self.temperature)

        except Exception as e:
            self._record_access("temp_read_error", str(e))

    def set_target_temperature(self, temp: float):
        """Set target temperature for simulation."""
        self.temperature = temp


class MockLCDI2CPlugin(MockI2CDevice):
    """Mock LCD display plugin with I2C operations."""

    def __init__(self, cbpi, lcd_id: str, address: int = 0x27):
        self.cbpi = cbpi
        self.lcd_id = lcd_id
        self.bus = MockSMBus(1)
        super().__init__(address, self.bus)

        self.display_lines = ["", "", "", ""]
        self.update_interval = 2.0
        self._running = False
        self._task = None

    async def start(self):
        """Start the LCD update loop."""
        self._running = True

        # Initialize LCD
        self._initialize_lcd()

        # Start update loop
        self._task = asyncio.create_task(self._update_loop())

    async def stop(self):
        """Stop the LCD update loop."""
        self._running = False
        if self._task:
            self._task.cancel()

    def _initialize_lcd(self):
        """Initialize the LCD display."""
        try:
            # LCD initialization sequence (simplified)
            init_commands = [0x33, 0x32, 0x28, 0x0C, 0x06, 0x01]
            for cmd in init_commands:
                self.bus.write_byte(self.address, cmd)
                self._record_access("lcd_init", cmd)

        except Exception as e:
            self._record_access("init_error", str(e))

    async def _update_loop(self):
        """Main LCD update loop."""
        while self._running:
            try:
                await self.update_display()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._record_access("update_error", str(e))
                await asyncio.sleep(1)  # Error recovery delay

    async def update_display(self):
        """Update LCD display."""
        try:
            # Get sensor values for display
            mash_temp = await self.cbpi.sensor.get_value("mash_temp")
            boil_temp = await self.cbpi.sensor.get_value("boil_temp")

            # Format display content
            self.display_lines[0] = "Brewmotron Status"
            self.display_lines[1] = "-" * 16
            self.display_lines[2] = f"Mash: {mash_temp:.1f}C"
            self.display_lines[3] = f"Boil: {boil_temp:.1f}C"

            # Send to display (simplified)
            for line_num, line in enumerate(self.display_lines):
                # Set cursor position
                cursor_pos = 0x80 + (line_num * 0x40)
                self.bus.write_byte(self.address, cursor_pos)

                # Write line data
                for char in line[:16]:  # Limit to 16 chars
                    self.bus.write_byte(self.address, ord(char))

            self._record_access("lcd_update", len("".join(self.display_lines)))

        except Exception as e:
            self._record_access("lcd_error", str(e))


class TestI2CBusCoordination:
    """Integration test suite for I2C bus coordination."""

    @pytest_asyncio.fixture
    async def i2c_harness(self):
        """Create a test harness with multiple I2C devices."""
        harness = PluginTestHarness()

        # Create multiple I2C devices
        devices = {
            "mash_display": Mock7SegI2CPlugin(harness.cbpi, "mash_display", 0x70),
            "boil_display": Mock7SegI2CPlugin(harness.cbpi, "boil_display", 0x71),
            "temp_sensor": MockTempSensorI2CPlugin(harness.cbpi, "mash_temp", 0x48, 0),
            "temp_sensor2": MockTempSensorI2CPlugin(harness.cbpi, "boil_temp", 0x48, 1),
            "lcd_display": MockLCDI2CPlugin(harness.cbpi, "main_lcd", 0x27),
        }

        # Register sensors in CBPI system
        harness.cbpi.sensor.register_sensor(
            "mash_temp", {"id": "mash_temp", "type": "MockTemp"}
        )
        harness.cbpi.sensor.register_sensor(
            "boil_temp", {"id": "boil_temp", "type": "MockTemp"}
        )

        yield {"harness": harness, "devices": devices}

        # Cleanup
        for device in devices.values():
            await device.stop()
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_concurrent_i2c_access(self, i2c_harness):
        """Test multiple devices accessing I2C bus concurrently."""
        devices = i2c_harness["devices"]

        # Start all devices
        start_tasks = [device.start() for device in devices.values()]
        await asyncio.gather(*start_tasks)

        # Run for test period
        await asyncio.sleep(5)

        # Verify all devices are making I2C transactions
        for device_name, device in devices.items():
            assert (
                device.transaction_count > 0
            ), f"{device_name} should have made I2C transactions"
            assert (
                device.last_access is not None
            ), f"{device_name} should have access timestamp"

        # Stop all devices
        stop_tasks = [device.stop() for device in devices.values()]
        await asyncio.gather(*stop_tasks)

    @pytest.mark.asyncio
    async def test_i2c_address_isolation(self, i2c_harness):
        """Test that devices with different I2C addresses don't interfere."""
        devices = i2c_harness["devices"]
        mash_display = devices["mash_display"]
        boil_display = devices["boil_display"]

        # Start displays
        await mash_display.start()
        await boil_display.start()

        # Set different values
        mash_display.set_value(65.5)
        boil_display.set_value(98.2)

        # Wait for updates
        await asyncio.sleep(2)

        # Check that each display maintains its own state
        mash_history = [
            h for h in mash_display.access_history if h["operation"] == "display_update"
        ]
        boil_history = [
            h for h in boil_display.access_history if h["operation"] == "display_update"
        ]

        assert len(mash_history) > 0, "Mash display should have update history"
        assert len(boil_history) > 0, "Boil display should have update history"

        # Verify values are different
        latest_mash = mash_history[-1]["data"]
        latest_boil = boil_history[-1]["data"]

        assert latest_mash != latest_boil, "Displays should maintain different values"
        assert (
            abs(latest_mash - 65.5) < 0.1
        ), f"Mash display should show ~65.5, got {latest_mash}"
        assert (
            abs(latest_boil - 98.2) < 0.1
        ), f"Boil display should show ~98.2, got {latest_boil}"

        await mash_display.stop()
        await boil_display.stop()

    @pytest.mark.asyncio
    async def test_shared_device_channel_coordination(self, i2c_harness):
        """Test multiple sensors sharing the same I2C device (different channels)."""
        devices = i2c_harness["devices"]
        temp_sensor = devices["temp_sensor"]  # channel 0
        temp_sensor2 = devices["temp_sensor2"]  # channel 1

        # Both sensors use same I2C address (0x48) but different channels
        assert (
            temp_sensor.address == temp_sensor2.address
        ), "Sensors should share same I2C address"
        assert (
            temp_sensor.channel != temp_sensor2.channel
        ), "Sensors should use different channels"

        # Start both sensors
        await temp_sensor.start()
        await temp_sensor2.start()

        # Set different target temperatures
        temp_sensor.set_target_temperature(66.0)
        temp_sensor2.set_target_temperature(99.0)

        # Wait for readings
        await asyncio.sleep(3)

        # Verify both sensors are reading independently
        mash_temp = await i2c_harness["harness"].cbpi.sensor.get_value("mash_temp")
        boil_temp = await i2c_harness["harness"].cbpi.sensor.get_value("boil_temp")

        assert (
            abs(mash_temp - 66.0) < 5.0
        ), f"Mash temp should be ~66°C, got {mash_temp}"
        assert (
            abs(boil_temp - 99.0) < 5.0
        ), f"Boil temp should be ~99°C, got {boil_temp}"
        assert (
            abs(mash_temp - boil_temp) > 10
        ), "Temperatures should be significantly different"

        await temp_sensor.stop()
        await temp_sensor2.stop()

    @pytest.mark.asyncio
    async def test_i2c_transaction_timing(self, i2c_harness):
        """Test I2C transaction timing and frequency."""
        devices = i2c_harness["devices"]
        mash_display = devices["mash_display"]
        temp_sensor = devices["temp_sensor"]

        # Configure different update intervals
        mash_display.update_interval = 0.5  # Fast updates
        temp_sensor.read_interval = 1.5  # Slower updates

        # Start devices
        await mash_display.start()
        await temp_sensor.start()

        # Run for measurement period
        start_time = datetime.now()
        await asyncio.sleep(5)
        end_time = datetime.now()

        # Analyze transaction timing
        display_updates = [
            h for h in mash_display.access_history if h["operation"] == "display_update"
        ]
        sensor_reads = [
            h
            for h in temp_sensor.access_history
            if h["operation"] == "temperature_read"
        ]

        # Calculate update rates
        duration = (end_time - start_time).total_seconds()
        display_rate = len(display_updates) / duration
        sensor_rate = len(sensor_reads) / duration

        # Verify rates match configured intervals
        expected_display_rate = 1.0 / mash_display.update_interval
        expected_sensor_rate = 1.0 / temp_sensor.read_interval

        assert (
            abs(display_rate - expected_display_rate) < 0.5
        ), f"Display rate should be ~{expected_display_rate:.1f}/s, got {display_rate:.1f}/s"
        assert (
            abs(sensor_rate - expected_sensor_rate) < 0.3
        ), f"Sensor rate should be ~{expected_sensor_rate:.1f}/s, got {sensor_rate:.1f}/s"

        await mash_display.stop()
        await temp_sensor.stop()

    @pytest.mark.asyncio
    async def test_i2c_error_recovery(self, i2c_harness):
        """Test I2C error handling and recovery."""
        devices = i2c_harness["devices"]
        mash_display = devices["mash_display"]

        # Start display
        await mash_display.start()
        await asyncio.sleep(1)

        # Record initial transaction count
        initial_count = mash_display.transaction_count

        # Simulate I2C bus error by disconnecting device
        mash_display.bus.set_device_connected(0x70, False)

        # Wait for error conditions
        await asyncio.sleep(2)

        # Should have error entries in history
        error_entries = [
            h for h in mash_display.access_history if "error" in h["operation"]
        ]
        assert len(error_entries) > 0, "Should have recorded I2C errors"

        # Restore device connection
        mash_display.bus.set_device_connected(0x70, True)

        # Wait for recovery
        await asyncio.sleep(2)

        # Should resume normal operation
        final_count = mash_display.transaction_count
        assert (
            final_count > initial_count
        ), "Should continue making transactions after recovery"

        await mash_display.stop()

    @pytest.mark.asyncio
    async def test_i2c_bus_contention_simulation(self, i2c_harness):
        """Test I2C bus behavior under high contention."""
        devices = i2c_harness["devices"]

        # Set aggressive update intervals to create contention
        for device in devices.values():
            if hasattr(device, "update_interval"):
                device.update_interval = 0.1  # Very fast updates
            if hasattr(device, "read_interval"):
                device.read_interval = 0.1

        # Start all devices simultaneously
        start_tasks = [device.start() for device in devices.values()]
        await asyncio.gather(*start_tasks)

        # Run under high contention
        await asyncio.sleep(3)

        # Check that all devices are still operating
        for device_name, device in devices.items():
            assert (
                device.transaction_count > 10
            ), f"{device_name} should have high transaction count under contention"

            # Check for reasonable error rate (some errors expected under high contention)
            error_count = len(
                [h for h in device.access_history if "error" in h["operation"]]
            )
            error_rate = (
                error_count / device.transaction_count
                if device.transaction_count > 0
                else 0
            )

            assert (
                error_rate < 0.5
            ), f"{device_name} error rate too high: {error_rate:.2f}"

        # Stop all devices
        stop_tasks = [device.stop() for device in devices.values()]
        await asyncio.gather(*stop_tasks)

    @pytest.mark.asyncio
    async def test_cross_device_data_flow(self, i2c_harness):
        """Test data flowing between I2C devices (sensor -> displays)."""
        devices = i2c_harness["devices"]
        temp_sensor = devices["temp_sensor"]
        mash_display = devices["mash_display"]
        lcd_display = devices["lcd_display"]

        # Start all devices
        await temp_sensor.start()
        await mash_display.start()
        await lcd_display.start()

        # Set sensor temperature
        temp_sensor.set_target_temperature(67.8)

        # Wait for data to propagate through system
        await asyncio.sleep(4)

        # Verify sensor reading
        sensor_value = await i2c_harness["harness"].cbpi.sensor.get_value("mash_temp")
        assert (
            abs(sensor_value - 67.8) < 2.0
        ), f"Sensor should read ~67.8°C, got {sensor_value}"

        # Set display to show sensor value
        mash_display.set_value(sensor_value)

        # Wait for display update
        await asyncio.sleep(1)

        # Check that display updated with sensor value
        display_updates = [
            h for h in mash_display.access_history if h["operation"] == "display_update"
        ]

        assert len(display_updates) > 0, "Display should have update history"
        latest_display_value = display_updates[-1]["data"]
        assert (
            abs(latest_display_value - sensor_value) < 1.0
        ), f"Display should show sensor value {sensor_value:.1f}, got {latest_display_value:.1f}"

        # Check LCD display updates
        lcd_updates = [
            h for h in lcd_display.access_history if h["operation"] == "lcd_update"
        ]
        assert len(lcd_updates) > 0, "LCD should have update history"

        await temp_sensor.stop()
        await mash_display.stop()
        await lcd_display.stop()

    @pytest.mark.asyncio
    async def test_i2c_transaction_ordering(self, i2c_harness):
        """Test that I2C transactions maintain proper ordering."""
        devices = i2c_harness["devices"]

        # Use devices that share the same bus for ordering test
        temp_sensor = devices["temp_sensor"]
        temp_sensor2 = devices["temp_sensor2"]

        # Start both sensors
        await temp_sensor.start()
        await temp_sensor2.start()

        # Run for sufficient time to get multiple transactions
        await asyncio.sleep(4)

        # Get all transactions from shared bus (address 0x48)
        all_transactions = []
        all_transactions.extend(temp_sensor.access_history)
        all_transactions.extend(temp_sensor2.access_history)

        # Sort by timestamp
        all_transactions.sort(key=lambda x: x["timestamp"])

        # Verify transactions are properly interleaved (not blocked)
        sensor1_count = len(
            [t for t in all_transactions if t in temp_sensor.access_history]
        )
        sensor2_count = len(
            [t for t in all_transactions if t in temp_sensor2.access_history]
        )

        assert (
            sensor1_count > 0 and sensor2_count > 0
        ), "Both sensors should have transactions"

        # Check for reasonable interleaving (no long sequences of same sensor)
        max_consecutive = 0
        current_consecutive = 1
        last_sensor = None

        for transaction in all_transactions:
            current_sensor = 1 if transaction in temp_sensor.access_history else 2

            if current_sensor == last_sensor:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1

            last_sensor = current_sensor

        # Should not have long sequences of same sensor (indicates blocking)
        assert (
            max_consecutive <= 5
        ), f"Too many consecutive transactions from same sensor: {max_consecutive}"

        await temp_sensor.stop()
        await temp_sensor2.stop()
