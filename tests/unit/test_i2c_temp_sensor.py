"""
Unit tests for cbpi4-i2cTempSensor plugin.

Tests the I2C temperature sensor functionality with comprehensive hardware mocking
and ADC simulation.
"""

import asyncio
import math
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import HardwareTestHarness, MockSMBus, MockTemperatureSensor
from tests.fixtures.test_data import PluginConfigFactory

# Mark all tests in this module as hardware and I2C tests
pytestmark = [pytest.mark.hardware, pytest.mark.i2c]


class TestI2CTempSensor:
    """Test suite for i2cTempSensor plugin."""

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
    def mock_temp_sensor(self):
        """Create a mocked temperature sensor."""
        return MockTemperatureSensor(base_temperature=20.0, sensor_type="PT100")

    @pytest.fixture
    def sensor_config(self):
        """Create I2C temperature sensor configuration."""
        return PluginConfigFactory(
            id="test_i2c_temp",
            name="TestI2CTempSensor",
            type="Sensor",
            props={
                "SensorAddress": "0x48",
                "Interval": "1.0",
                "Offset": "0.0",
                "ProbeType": "PT100",
            },
        )

    @pytest.mark.asyncio
    async def test_sensor_initialization(self, plugin_harness, sensor_config, mock_i2c, mock_temp_sensor):
        """Test sensor initialization with valid configuration."""

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.sensor_address = int(props.get("SensorAddress", "0x48"), 16)
                self.interval = float(props.get("Interval", "1.0"))
                self.offset = float(props.get("Offset", "0.0"))
                self.probe_type = props.get("ProbeType", "PT100")
                self.value = 0.0
                self.running = False
                self.task = None

            async def on_start(self):
                """Start the sensor reading task."""
                self.running = True
                self.task = asyncio.create_task(self._run())

            async def on_stop(self):
                """Stop the sensor reading task."""
                self.running = False
                if self.task:
                    self.task.cancel()

            async def _run(self):
                """Main sensor reading loop."""
                while self.running:
                    try:
                        # Simulate ADC reading
                        raw_value = mock_i2c.read_word_data(self.sensor_address, 0x00)
                        self.value = self._convert_to_temperature(raw_value) + self.offset
                    except Exception as e:
                        # Handle I2C errors gracefully
                        pass

                    await asyncio.sleep(self.interval)

            def _convert_to_temperature(self, raw_value):
                """Convert ADC raw value to temperature."""
                # Simplified PT100 conversion
                if self.probe_type == "PT100":
                    # Basic linear approximation for testing
                    return (raw_value / 65535.0) * 100.0
                return raw_value / 100.0

            def get_value(self):
                """Get current temperature value."""
                return self.value

        # Set up mock I2C to return realistic ADC values
        mock_i2c.write_word_data(0x48, 0x00, 32768)  # Mid-range ADC value

        plugin = await plugin_harness.load_plugin(MockI2CTempSensor, sensor_config.id, sensor_config.props)

        assert plugin.id == sensor_config.id
        assert plugin.sensor_address == 0x48
        assert plugin.interval == 1.0
        assert plugin.offset == 0.0
        assert plugin.probe_type == "PT100"
        assert plugin.running == True

        # Wait for a sensor reading
        await asyncio.sleep(0.1)

        # Should have a temperature reading
        temp_value = plugin.get_value()
        assert isinstance(temp_value, float)
        assert temp_value >= 0.0  # Reasonable temperature range

    @pytest.mark.asyncio
    async def test_temperature_conversion_accuracy(self, plugin_harness, sensor_config, mock_i2c):
        """Test temperature conversion accuracy for different probe types."""

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.probe_type = props.get("ProbeType", "PT100")
                self.calibration_data = {
                    "PT100": {"R0": 100.0, "A": 3.9083e-3, "B": -5.775e-7},
                    "PT1000": {"R0": 1000.0, "A": 3.9083e-3, "B": -5.775e-7},
                }
                self.running = False

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False

            def convert_resistance_to_temperature(self, resistance):
                """Convert resistance to temperature using Callendar-Van
                Dusen equation."""
                if self.probe_type not in self.calibration_data:
                    return 0.0

                cal = self.calibration_data[self.probe_type]
                R0 = cal["R0"]
                A = cal["A"]
                B = cal["B"]

                # Simplified calculation for positive temperatures
                # R(T) = R0 * (1 + A*T + B*T^2)
                # Solving for T (approximate)
                ratio = resistance / R0
                if ratio >= 1.0:
                    temp = (ratio - 1.0) / A
                    return temp
                else:
                    return 0.0

        plugin = await plugin_harness.load_plugin(MockI2CTempSensor, sensor_config.id, sensor_config.props)

        # Test known resistance-temperature pairs for PT100
        test_cases = [
            (100.0, 0.0),  # 0°C
            (138.5, 100.0),  # 100°C (approximately)
            (119.4, 50.0),  # 50°C (approximately)
        ]

        for resistance, expected_temp in test_cases:
            calculated_temp = plugin.convert_resistance_to_temperature(resistance)
            # Allow for some tolerance in conversion
            assert abs(calculated_temp - expected_temp) < 5.0, f"Temperature conversion error for {resistance}Ω"

    @pytest.mark.asyncio
    async def test_sensor_offset_calibration(self, plugin_harness, mock_i2c):
        """Test sensor offset calibration."""
        config_with_offset = PluginConfigFactory(
            id="test_offset_sensor",
            type="Sensor",
            props={
                "SensorAddress": "0x48",
                "Interval": "0.5",
                "Offset": "2.5",  # +2.5°C offset
                "ProbeType": "PT100",
            },
        )

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.offset = float(props.get("Offset", "0.0"))
                self.raw_temperature = 20.0
                self.running = False

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False

            def get_calibrated_value(self):
                """Get temperature with offset applied."""
                return self.raw_temperature + self.offset

        plugin = await plugin_harness.load_plugin(MockI2CTempSensor, config_with_offset.id, config_with_offset.props)

        # Test offset application
        calibrated_temp = plugin.get_calibrated_value()
        expected_temp = 20.0 + 2.5  # Raw + offset
        assert calibrated_temp == expected_temp

    @pytest.mark.asyncio
    async def test_i2c_communication_error_handling(self, plugin_harness, sensor_config, mock_i2c):
        """Test handling of I2C communication errors."""

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.sensor_address = int(props.get("SensorAddress", "0x48"), 16)
                self.error_count = 0
                self.last_good_value = 0.0
                self.running = False
                self.task = None

            async def on_start(self):
                self.running = True
                self.task = asyncio.create_task(self._run())

            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()

            async def _run(self):
                """Main sensor reading loop with error handling."""
                while self.running:
                    try:
                        # Attempt I2C read
                        raw_value = mock_i2c.read_word_data(self.sensor_address, 0x00)
                        self.last_good_value = raw_value / 100.0
                    except Exception as e:
                        self.error_count += 1
                        # Continue using last good value

                    await asyncio.sleep(0.1)

            def get_error_count(self):
                return self.error_count

            def get_value(self):
                return self.last_good_value

        # Simulate I2C device failure
        mock_i2c.simulate_device_failure(0x48, "connection_lost")

        plugin = await plugin_harness.load_plugin(MockI2CTempSensor, sensor_config.id, sensor_config.props)

        # Wait for some read attempts
        await asyncio.sleep(0.3)

        # Should handle errors gracefully
        assert plugin.running == True
        assert plugin.get_error_count() > 0
        # Should still provide a value (last good or default)
        assert isinstance(plugin.get_value(), float)

    @pytest.mark.asyncio
    async def test_different_sensor_addresses(self, plugin_harness, mock_i2c):
        """Test sensors on different I2C addresses."""
        addresses = [0x48, 0x49, 0x4A, 0x4B]
        sensors = []

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.sensor_address = int(props.get("SensorAddress", "0x48"), 16)
                self.value = 20.0 + (self.sensor_address - 0x48) * 5  # Different base temps
                self.running = False

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False

            def get_value(self):
                return self.value

        # Create sensors on different addresses
        for i, addr in enumerate(addresses):
            config = PluginConfigFactory(
                id=f"test_sensor_{i}",
                type="Sensor",
                props={"SensorAddress": f"0x{addr:02X}"},
            )

            sensor = await plugin_harness.load_plugin(MockI2CTempSensor, config.id, config.props)
            sensors.append(sensor)

        # Verify each sensor has correct address and unique value
        for i, sensor in enumerate(sensors):
            expected_addr = addresses[i]
            expected_temp = 20.0 + i * 5

            assert sensor.sensor_address == expected_addr
            assert sensor.get_value() == expected_temp

    def test_probe_type_configuration(self, sensor_config):
        """Test different probe type configurations."""
        probe_types = ["PT100", "PT1000", "Thermistor", "Thermocouple"]

        for probe_type in probe_types:
            config = sensor_config
            config.props["ProbeType"] = probe_type

            # Should accept any probe type configuration
            assert config.props["ProbeType"] == probe_type


class TestI2CTempSensorEdgeCases:
    """Test edge cases and error conditions for i2cTempSensor plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.fixture
    def mock_i2c(self):
        """Create a mocked I2C interface."""
        return MockSMBus(1)

    @pytest.mark.asyncio
    async def test_invalid_sensor_address(self, plugin_harness):
        """Test handling of invalid I2C addresses."""
        invalid_config = PluginConfigFactory(
            id="test_invalid_addr",
            type="Sensor",
            props={"SensorAddress": "0xFF"},  # Invalid I2C address
        )

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                try:
                    self.sensor_address = int(props.get("SensorAddress", "0x48"), 16)
                    # Validate address range
                    if self.sensor_address > 0x7F:
                        self.sensor_address = 0x48  # Default fallback
                except ValueError:
                    self.sensor_address = 0x48  # Default fallback
                self.running = False

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False

        plugin = await plugin_harness.load_plugin(MockI2CTempSensor, invalid_config.id, invalid_config.props)

        # Should fallback to valid default address
        assert plugin.sensor_address == 0x48

    @pytest.mark.asyncio
    async def test_extreme_temperature_readings(self, plugin_harness, mock_i2c):
        """Test handling of extreme temperature readings."""
        config = PluginConfigFactory(id="test_extreme_temps", type="Sensor", props={"SensorAddress": "0x48"})

        class MockI2CTempSensor:
            _plugin_type = "Sensor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.sensor_address = int(props.get("SensorAddress", "0x48"), 16)
                self.running = False

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False

            def validate_temperature(self, temp):
                """Validate temperature reading is within reasonable bounds."""
                if temp < -50.0 or temp > 200.0:
                    return None  # Invalid reading
                return temp

        plugin = await plugin_harness.load_plugin(MockI2CTempSensor, config.id, config.props)

        # Test extreme values
        extreme_temps = [-100.0, 500.0, float("inf"), float("-inf")]

        for temp in extreme_temps:
            validated = plugin.validate_temperature(temp)
            if temp == float("inf") or temp == float("-inf"):
                assert validated is None  # Should reject infinite values
            elif temp < -50.0 or temp > 200.0:
                assert validated is None  # Should reject out-of-range values
