"""
Pytest configuration and shared fixtures for Brewmotron testing.

This module provides the foundational test configuration, fixtures, and utilities
for testing all Brewmotron CraftBeerPi4 plugins.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest import FixtureRequest

# Add plugin directories to Python path for testing
PROJECT_ROOT = Path(__file__).parent.parent
PLUGIN_DIRS = [
    PROJECT_ROOT / "cbpi4-7SegDisplay",
    PROJECT_ROOT / "cbpi4-LCDisplay",
    PROJECT_ROOT / "cbpi4-i2cTempSensor",
    PROJECT_ROOT / "cbpi4-GPIOInput",
    PROJECT_ROOT / "cbpi4-AlwaysONGPIO",
    PROJECT_ROOT / "cbpi4-BMT-Key",
    PROJECT_ROOT / "cbpi4-BMT-MomentaryButtons",
    PROJECT_ROOT / "cbpi4-InternetConnectedGPIO",
    PROJECT_ROOT / "cbpi4-OneAtATime",
    PROJECT_ROOT / "cbpi4-NOR3",
]

for plugin_dir in PLUGIN_DIRS:
    if plugin_dir.exists():
        sys.path.insert(0, str(plugin_dir))

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Disable noisy loggers during testing
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# =============================================================================
# Test Configuration
# =============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "hardware: mark test as requiring hardware simulation")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "manual: mark test as requiring manual execution (skipped in CI)")
    config.addinivalue_line("markers", "i2c: mark test as requiring I2C hardware")
    config.addinivalue_line("markers", "gpio: mark test as requiring GPIO hardware")
    config.addinivalue_line("markers", "network: mark test as requiring network connectivity")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to apply markers automatically."""
    for item in items:
        # Mark tests in specific directories
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark hardware-dependent tests
        if any(hw in item.name.lower() for hw in ["gpio", "i2c", "sensor", "display"]):
            item.add_marker(pytest.mark.hardware)

        # Mark slow tests
        if any(slow in item.name.lower() for slow in ["stress", "performance", "long"]):
            item.add_marker(pytest.mark.slow)


# =============================================================================
# Hardware Mocking Fixtures
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def mock_hardware_environment():
    """Automatically mock all hardware dependencies for the test session."""
    patches = []

    # Mock RPi.GPIO
    rpi_mock = MagicMock()
    rpi_mock.BCM = 11
    rpi_mock.IN = 1
    rpi_mock.OUT = 0
    rpi_mock.HIGH = 1
    rpi_mock.LOW = 0
    rpi_mock.PUD_UP = 22
    rpi_mock.PUD_DOWN = 21

    # Mock GPIO functions
    rpi_mock.setmode = MagicMock()
    rpi_mock.setup = MagicMock()
    rpi_mock.output = MagicMock()
    rpi_mock.input = MagicMock(return_value=0)
    rpi_mock.cleanup = MagicMock()
    rpi_mock.getmode = MagicMock(return_value=None)

    gpio_patches = [
        patch.dict("sys.modules", {"RPi": MagicMock(), "RPi.GPIO": rpi_mock}),
        patch("RPi.GPIO", rpi_mock),
    ]

    # Mock SMBus for I2C
    smbus_mock = MagicMock()
    smbus_mock.SMBus = MagicMock()
    smbus_patches = [
        patch.dict("sys.modules", {"smbus": smbus_mock}),
        patch("smbus.SMBus", smbus_mock.SMBus),
    ]

    # Mock Adafruit libraries
    adafruit_mock = MagicMock()
    adafruit_patches = [
        patch.dict(
            "sys.modules",
            {
                "busio": MagicMock(),
                "adafruit_ht16k33": MagicMock(),
                "adafruit_ht16k33.segments": MagicMock(),
                "board": MagicMock(),
                "digitalio": MagicMock(),
            },
        )
    ]

    # Mock RPLCD for LCD display
    rplcd_patches = [patch.dict("sys.modules", {"RPLCD": MagicMock(), "RPLCD.i2c": MagicMock()})]

    all_patches = gpio_patches + smbus_patches + adafruit_patches + rplcd_patches

    # Start all patches
    for patch_obj in all_patches:
        patches.append(patch_obj.start())

    yield

    # Stop all patches
    for patch_obj in all_patches:
        patch_obj.stop()


@pytest.fixture
def mock_gpio():
    """Provide a mock GPIO interface for individual tests."""
    with patch("RPi.GPIO") as gpio_mock:
        gpio_mock.BCM = 11
        gpio_mock.IN = 1
        gpio_mock.OUT = 0
        gpio_mock.HIGH = 1
        gpio_mock.LOW = 0
        gpio_mock.PUD_UP = 22
        gpio_mock.PUD_DOWN = 21

        # Track GPIO states
        gpio_mock._pin_states = {}
        gpio_mock._pin_modes = {}

        def setup_side_effect(pin, mode, **kwargs):
            gpio_mock._pin_modes[pin] = mode
            if mode == gpio_mock.OUT:
                gpio_mock._pin_states[pin] = gpio_mock.LOW

        def output_side_effect(pin, value):
            if pin in gpio_mock._pin_modes and gpio_mock._pin_modes[pin] == gpio_mock.OUT:
                gpio_mock._pin_states[pin] = value

        def input_side_effect(pin):
            return gpio_mock._pin_states.get(pin, gpio_mock.LOW)

        gpio_mock.setup.side_effect = setup_side_effect
        gpio_mock.output.side_effect = output_side_effect
        gpio_mock.input.side_effect = input_side_effect

        yield gpio_mock


@pytest.fixture
def mock_i2c_bus():
    """Provide a mock I2C bus for testing I2C-dependent plugins."""
    bus_mock = MagicMock()

    # Simulate I2C device responses
    bus_mock._device_data = {
        0x70: {},  # 7-segment display 1
        0x71: {},  # 7-segment display 2
        0x72: {},  # 7-segment display 3
        0x48: {},  # ADS1115 ADC
    }

    def read_byte_data_side_effect(addr, reg):
        return bus_mock._device_data.get(addr, {}).get(reg, 0)

    def write_byte_data_side_effect(addr, reg, value):
        if addr not in bus_mock._device_data:
            bus_mock._device_data[addr] = {}
        bus_mock._device_data[addr][reg] = value

    bus_mock.read_byte_data.side_effect = read_byte_data_side_effect
    bus_mock.write_byte_data.side_effect = write_byte_data_side_effect

    with patch("smbus.SMBus", return_value=bus_mock):
        yield bus_mock


# =============================================================================
# CraftBeerPi4 Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_cbpi():
    """Provide a mock CraftBeerPi4 instance for testing plugins."""
    cbpi_mock = AsyncMock()

    # Mock configuration system
    cbpi_mock.config = AsyncMock()
    cbpi_mock.config.get = AsyncMock(return_value="default_value")
    cbpi_mock.config.set = AsyncMock()

    # Mock actor system
    cbpi_mock.actor = AsyncMock()
    cbpi_mock.actor.get_state = AsyncMock(return_value=False)
    cbpi_mock.actor.set_state = AsyncMock()
    cbpi_mock.actor.on = AsyncMock()
    cbpi_mock.actor.off = AsyncMock()

    # Mock sensor system
    cbpi_mock.sensor = AsyncMock()
    cbpi_mock.sensor.get_value = AsyncMock(return_value=20.0)

    # Mock step system
    cbpi_mock.step = AsyncMock()

    # Mock recipe system
    cbpi_mock.recipe = AsyncMock()

    # Mock notification system
    cbpi_mock.notification = AsyncMock()
    cbpi_mock.notification.notify = AsyncMock()

    # Mock websocket system
    cbpi_mock.ws = AsyncMock()
    cbpi_mock.ws.send = AsyncMock()

    return cbpi_mock


@pytest.fixture
def mock_cbpi_plugin_base():
    """Mock the base CBPi plugin classes."""
    with (
        patch("cbpi.api.CBPiActor") as actor_mock,
        patch("cbpi.api.CBPiSensor") as sensor_mock,
        patch("cbpi.api.CBPiExtension") as extension_mock,
    ):

        # Configure base class mocks
        actor_mock.return_value = AsyncMock()
        sensor_mock.return_value = AsyncMock()
        extension_mock.return_value = AsyncMock()

        yield {
            "CBPiActor": actor_mock,
            "CBPiSensor": sensor_mock,
            "CBPiExtension": extension_mock,
        }


# =============================================================================
# Async Testing Fixtures
# =============================================================================


@pytest.fixture
def event_loop():
    """Create an event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_mock_cbpi(mock_cbpi):
    """Async version of the CBPi mock for async tests."""
    return mock_cbpi


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_plugin_config():
    """Provide sample plugin configuration data."""
    return {
        "name": "TestPlugin",
        "version": "1.0.0",
        "active": True,
        "type": "Actor",
        "props": {"GPIO": 18, "Inverted": "No"},
    }


@pytest.fixture
def sample_sensor_data():
    """Provide sample sensor reading data."""
    return {
        "temperature": 65.5,
        "timestamp": "2025-07-31T12:00:00Z",
        "unit": "C",
        "sensor_id": "temp_sensor_1",
    }


@pytest.fixture
def sample_brewing_config():
    """Provide sample brewing process configuration."""
    return {
        "mash_temp": 65.0,
        "boil_temp": 100.0,
        "ferment_temp": 18.0,
        "mash_time": 60,
        "boil_time": 60,
        "hop_additions": [
            {"time": 60, "amount": "20g", "type": "bittering"},
            {"time": 15, "amount": "15g", "type": "aroma"},
        ],
    }


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary configuration file for testing."""
    config_file = tmp_path / "test_config.yaml"
    config_data = """
    plugins:
      - name: TestPlugin
        active: true
        config:
          gpio_pin: 18
          inverted: false
    """
    config_file.write_text(config_data)
    return config_file


@pytest.fixture
def capture_logs():
    """Capture log messages during test execution."""
    import logging
    from io import StringIO

    log_capture_string = StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)

    # Get the root logger
    logger = logging.getLogger()
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)

    yield log_capture_string

    logger.removeHandler(ch)


# =============================================================================
# Parametrized Test Data
# =============================================================================


@pytest.fixture(params=[18, 19, 20, 21])
def gpio_pin(request):
    """Parametrized GPIO pin numbers for testing."""
    return request.param


@pytest.fixture(params=[0x70, 0x71, 0x72, 0x73])
def i2c_address(request):
    """Parametrized I2C addresses for testing."""
    return request.param


@pytest.fixture(params=[True, False])
def inverted_logic(request):
    """Parametrized inverted logic settings."""
    return request.param


# =============================================================================
# Performance Testing Fixtures
# =============================================================================


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during test execution."""
    import time

    import psutil

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.start_memory = None

        def start(self):
            self.start_time = time.time()
            self.start_memory = psutil.Process().memory_info().rss

        def stop(self):
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss

            return {
                "duration": end_time - self.start_time,
                "memory_delta": end_memory - self.start_memory,
                "peak_memory": end_memory,
            }

    return PerformanceMonitor()


# =============================================================================
# Plugin-Specific Fixtures
# =============================================================================


@pytest.fixture
def mock_7seg_display():
    """Mock 7-segment display hardware for testing."""
    display_mock = MagicMock()
    display_mock.brightness = 1.0
    display_mock.fill = MagicMock()
    display_mock.print = MagicMock()
    display_mock.show = MagicMock()

    with patch("adafruit_ht16k33.segments.Seg7x4", return_value=display_mock):
        yield display_mock


@pytest.fixture
def mock_lcd_display():
    """Mock LCD display hardware for testing."""
    lcd_mock = MagicMock()
    lcd_mock.write_string = MagicMock()
    lcd_mock.clear = MagicMock()
    lcd_mock.cursor_pos = (0, 0)

    with patch("RPLCD.i2c.CharLCD", return_value=lcd_mock):
        yield lcd_mock


@pytest.fixture
def mock_temperature_sensor():
    """Mock temperature sensor for testing."""
    sensor_mock = MagicMock()

    # Simulate realistic temperature readings
    import random

    base_temp = 20.0

    def read_temperature():
        # Add some realistic noise
        return base_temp + random.uniform(-0.5, 0.5)

    sensor_mock.read_temperature = read_temperature

    return sensor_mock


# =============================================================================
# I2C Coordinator and Cache Handler Fixtures with Guaranteed Cleanup
# =============================================================================


@pytest.fixture
async def i2c_coordinator():
    """
    Provide I2C coordinator with guaranteed cleanup and timeout protection.

    This fixture ensures that the I2C coordinator is properly stopped even if
    tests fail or hang, preventing background task leaks.
    """
    from brewmotron_cache_handler.i2c_coordinator import I2CCoordinator

    coordinator = I2CCoordinator()
    yield coordinator

    # Guaranteed cleanup with timeout and cancellation
    if coordinator._running:
        try:
            await asyncio.wait_for(coordinator.stop(), timeout=2.0)
        except asyncio.TimeoutError:
            logging.warning("Coordinator stop timeout - forcing cancellation")
            if coordinator._processor_task and not coordinator._processor_task.done():
                coordinator._processor_task.cancel()
                try:
                    await coordinator._processor_task
                except asyncio.CancelledError:
                    pass


@pytest.fixture
async def cache_handler():
    """
    Provide cache handler with guaranteed cleanup and timeout protection.

    This fixture ensures that the cache handler (and its internal I2C coordinator)
    is properly stopped even if tests fail or hang.
    """
    from brewmotron_cache_handler import CBPI4CacheHandler

    handler = CBPI4CacheHandler()
    yield handler

    # Guaranteed cleanup
    if handler._running:
        try:
            await asyncio.wait_for(handler.stop(), timeout=2.0)
        except asyncio.TimeoutError:
            logging.warning("Cache handler stop timeout")
