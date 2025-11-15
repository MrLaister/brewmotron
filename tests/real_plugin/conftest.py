"""
Shared fixtures and configuration for real plugin tests.

This module provides the infrastructure to test ACTUAL plugin code
(not mocks) with hardware dependencies properly mocked out.
"""

import sys
from pathlib import Path
from unittest import mock

import pytest
import pytest_asyncio

# Import our test infrastructure
from tests.fixtures.cbpi_mock import (
    PluginTestHarness,
    MockCBPiActorBase,
    MockCBPiSensorBase,
    MockCBPiExtensionBase,
    MockProperty,
)
from tests.fixtures.hardware_mocks import (
    HardwareTestHarness,
    Mock7SegmentDisplay,
    MockLCDisplay,
    MockRPiGPIO,
    MockSMBus,
    MockTemperatureSensor,
)


# =============================================================================
# Global Module Mocking (before any plugins are imported)
# =============================================================================

# Mock cbpi.api module at import time so plugins can load
_mock_cbpi_api = mock.MagicMock()
_mock_cbpi_api.CBPiActor = MockCBPiActorBase
_mock_cbpi_api.CBPiSensor = MockCBPiSensorBase
_mock_cbpi_api.CBPiExtension = MockCBPiExtensionBase
_mock_cbpi_api.Property = MockProperty
_mock_cbpi_api.parameters = mock.MagicMock()
_mock_cbpi_api.CBPiBase = mock.MagicMock()

# Install mocks globally
sys.modules["cbpi"] = mock.MagicMock()
sys.modules["cbpi.api"] = _mock_cbpi_api
sys.modules["cbpi.api.config"] = mock.MagicMock()
sys.modules["cbpi.api.actor"] = mock.MagicMock(CBPiActor=MockCBPiActorBase)
sys.modules["cbpi.api.base"] = mock.MagicMock()
sys.modules["cbpi.api.dataclasses"] = mock.MagicMock()
sys.modules["cbpi.api.step"] = mock.MagicMock()
sys.modules["cbpi.api.sensor"] = mock.MagicMock(CBPiSensor=MockCBPiSensorBase)


# =============================================================================
# Plugin Path Management
# =============================================================================


def get_plugin_path(plugin_name: str) -> Path:
    """
    Get the path to a plugin's source directory.

    Args:
        plugin_name: Plugin name like "7SegDisplay" or "GPIOInput"

    Returns:
        Path to the plugin's source code

    Example:
        >>> path = get_plugin_path("7SegDisplay")
        >>> # Returns: /path/to/cbpi4-7SegDisplay/cbpi4-7SegDisplay
    """
    repo_root = Path(__file__).parent.parent.parent
    plugin_dir = repo_root / f"cbpi4-{plugin_name}"
    source_dir = plugin_dir / f"cbpi4-{plugin_name}"

    if not source_dir.exists():
        raise FileNotFoundError(
            f"Plugin source not found: {source_dir}\n"
            f"Expected structure: cbpi4-{plugin_name}/cbpi4-{plugin_name}/__init__.py"
        )

    return source_dir


def add_plugin_to_path(plugin_name: str) -> None:
    """
    Add a plugin's directory to sys.path so it can be imported.

    Args:
        plugin_name: Plugin name like "7SegDisplay"
    """
    plugin_path = get_plugin_path(plugin_name).parent
    plugin_path_str = str(plugin_path)

    if plugin_path_str not in sys.path:
        sys.path.insert(0, plugin_path_str)


# =============================================================================
# Hardware Mocking Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def mock_rpi_gpio():
    """
    Automatically mock RPi.GPIO for all real plugin tests.

    This prevents tests from trying to access actual GPIO pins.
    """
    mock_gpio = MockRPiGPIO()

    # Mock cbpi.api module which plugins import
    from tests.fixtures.cbpi_mock import (
        MockCBPi,
        MockCBPiActorBase,
        MockCBPiSensorBase,
        MockCBPiExtensionBase,
        MockProperty,
    )

    mock_cbpi_api = mock.MagicMock()
    # Add the common classes that plugins use
    mock_cbpi_api.CBPiActor = MockCBPiActorBase
    mock_cbpi_api.CBPiSensor = MockCBPiSensorBase
    mock_cbpi_api.CBPiExtension = MockCBPiExtensionBase
    mock_cbpi_api.Property = MockProperty
    mock_cbpi_api.parameters = mock.MagicMock()
    mock_cbpi_api.CBPiBase = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "RPi": mock.MagicMock(),
            "RPi.GPIO": mock_gpio,
            "cbpi": mock.MagicMock(),
            "cbpi.api": mock_cbpi_api,
            "cbpi.api.config": mock.MagicMock(),
            "cbpi.api.actor": mock.MagicMock(CBPiActor=MockCBPiActorBase),
            "cbpi.api.base": mock.MagicMock(CBPiBase=mock.MagicMock()),
            "cbpi.api.dataclasses": mock.MagicMock(),
            "cbpi.api.step": mock.MagicMock(),
        },
    ):
        yield mock_gpio


@pytest.fixture
def mock_smbus():
    """
    Provide a mocked SMBus (I2C) interface.

    Returns:
        MockSMBus instance for testing I2C communication
    """
    return MockSMBus(1)


@pytest.fixture
def mock_i2c_devices(mock_smbus):
    """
    Provide pre-configured I2C devices (displays, sensors).

    Returns:
        Dict of I2C addresses to mock devices
    """
    return {
        0x70: Mock7SegmentDisplay(0x70),  # Sparge display
        0x71: Mock7SegmentDisplay(0x71),  # Mash display
        0x72: Mock7SegmentDisplay(0x72),  # Boil display
        0x27: MockLCDisplay(address=0x27),  # LCD display
    }


@pytest.fixture(autouse=True)
def mock_adafruit_hardware():
    """
    Automatically mock Adafruit hardware libraries.

    Mocks:
    - busio (I2C bus interface)
    - adafruit_ht16k33.segments (7-segment display)
    - adafruit_ads1x15 (ADC for temperature sensors)
    """
    # Mock busio I2C
    mock_i2c = mock.MagicMock()
    mock_board = mock.MagicMock()
    mock_board.SCL = "SCL"
    mock_board.SDA = "SDA"

    # Mock 7-segment display
    mock_segment_display = mock.MagicMock()

    # Mock ADS1115 ADC
    mock_ads = mock.MagicMock()
    mock_analog_in = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "busio": mock.MagicMock(I2C=lambda *args, **kwargs: mock_i2c),
            "board": mock_board,
            "adafruit_ht16k33": mock.MagicMock(),
            "adafruit_ht16k33.segments": mock.MagicMock(Seg7x4=lambda *args, **kwargs: mock_segment_display),
            "adafruit_ads1x15": mock.MagicMock(),
            "adafruit_ads1x15.ads1115": mock.MagicMock(ADS1115=lambda *args: mock_ads),
            "adafruit_ads1x15.analog_in": mock.MagicMock(AnalogIn=lambda *args: mock_analog_in),
        },
    ):
        yield {
            "i2c": mock_i2c,
            "board": mock_board,
            "segment_display": mock_segment_display,
            "ads1115": mock_ads,
            "analog_in": mock_analog_in,
        }


@pytest.fixture(autouse=True)
def mock_smbus_module(mock_smbus):
    """
    Automatically mock the smbus module to return our mock SMBus.
    """
    with mock.patch("smbus.SMBus", return_value=mock_smbus):
        yield mock_smbus


# =============================================================================
# Plugin Test Harness Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def plugin_harness():
    """
    Provide a PluginTestHarness for loading and testing real plugins.

    Yields:
        PluginTestHarness instance

    Example:
        async def test_my_plugin(plugin_harness):
            plugin = await plugin_harness.load_plugin(
                MyRealPlugin,
                "test_id",
                {"GPIO": "18"}
            )
            # Test the real plugin
    """
    harness = PluginTestHarness()
    yield harness
    await harness.cleanup()


@pytest_asyncio.fixture
async def hardware_harness():
    """
    Provide a HardwareTestHarness for complex hardware scenarios.

    Yields:
        HardwareTestHarness instance with pre-configured devices
    """
    harness = HardwareTestHarness()
    yield harness
    # Cleanup if needed


# =============================================================================
# Plugin Loader Helpers
# =============================================================================


@pytest.fixture
def plugin_loader():
    """
    Provide a helper function to load real plugins with automatic path management.

    Returns:
        Function that loads plugins by name

    Example:
        def test_something(plugin_loader):
            SSDisplay = plugin_loader("7SegDisplay", "SSDisplay")
            # Now you can instantiate SSDisplay
    """

    def load_plugin_class(plugin_name: str, class_name: str):
        """
        Load a real plugin class from its module.

        Args:
            plugin_name: Plugin directory name (e.g., "7SegDisplay")
            class_name: Class to import (e.g., "SSDisplay")

        Returns:
            Plugin class

        Raises:
            ImportError: If plugin cannot be imported
        """
        import importlib

        # Add plugin to path
        add_plugin_to_path(plugin_name)

        # Import the module - needs to import the nested module
        module_name = f"cbpi4-{plugin_name}.cbpi4-{plugin_name}"

        try:
            # Import the nested module where the class actually lives
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(
                f"Failed to import {class_name} from {module_name}: {e}\n"
                f"Make sure the plugin exists at: {get_plugin_path(plugin_name)}"
            )

    return load_plugin_class


# =============================================================================
# Common Test Data
# =============================================================================


@pytest.fixture
def standard_gpio_config():
    """Standard GPIO pin configuration for testing."""
    return {
        "GPIO": "18",
        "Inverted": "No",
    }


@pytest.fixture
def standard_display_config():
    """Standard 7-segment display configuration."""
    return {
        "SpargeAddress": "0x70",
        "BoilerAddress": "0x71",
        "MashAddress": "0x72",
        "RefreshRate": "1.0",
    }


@pytest.fixture
def standard_lcd_config():
    """Standard LCD display configuration."""
    return {
        "LCDAddress": "0x27",
        "RefreshRate": "1.0",
        "Charmap": "A00",
    }


# =============================================================================
# Markers for Test Organization
# =============================================================================


def pytest_configure(config):
    """Register custom markers for real plugin tests."""
    config.addinivalue_line("markers", "real_plugin: marks tests as testing real plugin code (not mocks)")
    config.addinivalue_line("markers", "requires_hardware_mock: marks tests requiring hardware mocking")
