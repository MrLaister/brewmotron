# Real Plugin Testing Framework

## Overview

This directory contains tests for **ACTUAL PRODUCTION PLUGIN CODE** (not mocks). These tests import the real plugin classes from `cbpi4-*` directories and test them with hardware dependencies mocked.

### Why Real Plugin Tests?

The tests in `tests/unit/` and `tests/integration/` currently test **mock implementations** created inside the test files. They verify patterns and coordination logic but provide **0% coverage** of actual plugin code.

Real plugin tests:
- ✅ Import actual plugin classes from production code
- ✅ Test real plugin logic, not simplified mocks
- ✅ Catch bugs in production code
- ✅ Provide regression protection during refactoring
- ✅ Verify hardware interaction patterns

## Quick Start

### Running Real Plugin Tests

```bash
# Run all real plugin tests
python3 -m pytest tests/real_plugin/ -v

# Run tests for specific plugin
python3 -m pytest tests/real_plugin/test_real_gpio_input.py -v

# Run with coverage of production code
python3 -m pytest tests/real_plugin/ \
    --cov=cbpi4-GPIOInput/cbpi4-GPIOInput \
    --cov=cbpi4-AlwaysONGPIO/cbpi4-AlwaysONGPIO \
    --cov-report=html

# Run only real plugin tests (using marker)
python3 -m pytest -m real_plugin -v
```

### Test Structure

```
tests/real_plugin/
├── conftest.py              # Shared fixtures and hardware mocking
├── README.md                # This file
├── test_real_always_on_gpio.py   # Example: Simple extension
├── test_real_gpio_input.py       # Example: Actor plugin
└── test_real_7seg_display.py     # Example: Complex extension with I2C
```

## Writing Real Plugin Tests

### Basic Pattern

```python
"""
Real plugin tests for cbpi4-YourPlugin.

Tests the ACTUAL YourPlugin code with mocked hardware.
"""

import pytest
import pytest_asyncio
from tests.fixtures.cbpi_mock import PluginTestHarness

pytestmark = [pytest.mark.real_plugin, pytest.mark.requires_hardware_mock]


@pytest.fixture
def real_your_plugin_class(plugin_loader):
    """Load the REAL plugin class."""
    # plugin_loader provided by conftest.py
    # Args: (plugin_directory_name, class_name)
    return plugin_loader("YourPlugin", "YourPluginClass")


class TestRealYourPlugin:
    """Test suite for the REAL YourPlugin."""

    @pytest.mark.asyncio
    async def test_plugin_initialization(
        self, plugin_harness, real_your_plugin_class
    ):
        """Test that real plugin initializes."""

        # Configuration for the plugin
        props = {
            "GPIO": "18",
            "SomeConfig": "value",
        }

        # Load the REAL plugin
        plugin = await plugin_harness.load_plugin(
            real_your_plugin_class,
            "test_plugin_id",
            props
        )

        # Test real plugin behavior
        assert plugin is not None
        # Add your assertions...
```

### Plugin Types

#### Testing an Actor Plugin

Actors receive: `cbpi`, `id`, `props`

```python
@pytest.fixture
def real_actor_class(plugin_loader):
    return plugin_loader("GPIOInput", "GPIOInput")


async def test_actor_on_off(plugin_harness, real_actor_class, mock_rpi_gpio):
    props = {"GPIO": "18", "Inverted": "No"}

    actor = await plugin_harness.load_plugin(
        real_actor_class,
        "test_actor",
        props
    )

    # Test actor methods
    await actor.on()
    assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH

    await actor.off()
    assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.LOW
```

#### Testing an Extension Plugin

Extensions receive: `cbpi` only (no id or props)

```python
@pytest.fixture
def real_extension_class(plugin_loader):
    return plugin_loader("7SegDisplay", "SSDisplay")


async def test_extension(plugin_harness, real_extension_class):
    # Extensions read config from cbpi.config
    plugin_harness.cbpi.config._config_data.update({
        "MashAddress": "0x72",
        "RefreshRate": "1.0",
    })

    extension = await plugin_harness.load_plugin(
        real_extension_class,
        "test_extension",
        {}  # Extensions don't use props
    )

    # Test extension behavior
    await asyncio.sleep(1.0)  # Let background tasks run
```

#### Testing a Sensor Plugin

Sensors receive: `cbpi`, `id`, `props`

```python
@pytest.fixture
def real_sensor_class(plugin_loader):
    return plugin_loader("i2cTempSensor", "I2CTempSensor")


async def test_sensor_reading(plugin_harness, real_sensor_class):
    props = {
        "Address": "0x48",
        "Offset": "0.0",
    }

    sensor = await plugin_harness.load_plugin(
        real_sensor_class,
        "test_sensor",
        props
    )

    # Get sensor reading
    value = await sensor.get_value()
    assert isinstance(value, float)
```

## Available Fixtures

### Provided by `conftest.py`

#### Hardware Mocking (Auto-Applied)

```python
mock_rpi_gpio       # Mocked RPi.GPIO module
mock_smbus          # Mocked SMBus (I2C) interface
mock_adafruit_hardware  # Mocked Adafruit libraries
mock_i2c_devices    # Pre-configured I2C devices (displays, etc.)
```

#### Plugin Loading

```python
plugin_harness      # PluginTestHarness for loading plugins
plugin_loader       # Function to load plugin classes
hardware_harness    # HardwareTestHarness for complex scenarios
```

#### Common Configurations

```python
standard_gpio_config     # Standard GPIO pin configuration
standard_display_config  # Standard 7-segment display config
standard_lcd_config      # Standard LCD display config
```

### Example: Using Fixtures

```python
@pytest.mark.asyncio
async def test_with_mocked_gpio(
    plugin_harness,
    real_gpio_input_class,
    mock_rpi_gpio,
    standard_gpio_config
):
    """Example showing fixture usage."""

    # Load plugin with standard config
    plugin = await plugin_harness.load_plugin(
        real_gpio_input_class,
        "test_id",
        standard_gpio_config
    )

    # Test with mocked GPIO
    await plugin.on()

    # Access mock state
    gpio_pin = int(standard_gpio_config["GPIO"])
    assert mock_rpi_gpio._pin_states[gpio_pin] == mock_rpi_gpio.HIGH
```

## Common Testing Patterns

### 1. Initialization Testing

```python
async def test_plugin_loads():
    """Verify plugin structure and initialization."""
    plugin = await plugin_harness.load_plugin(PluginClass, "id", props)

    assert plugin is not None
    assert hasattr(plugin, 'cbpi')
    assert plugin.id == "id"
    assert plugin.props == props
```

### 2. State Management Testing

```python
async def test_actor_state():
    """Test actor state transitions."""
    actor = await plugin_harness.load_plugin(ActorClass, "actor", props)

    # Test ON state
    await actor.on()
    assert await actor.get_state() is True

    # Test OFF state
    await actor.off()
    assert await actor.get_state() is False
```

### 3. Configuration Parsing Testing

```python
async def test_config_parsing():
    """Test that plugin correctly parses configuration."""
    props = {
        "GPIO": "21",
        "Inverted": "Yes",
    }

    plugin = await plugin_harness.load_plugin(PluginClass, "id", props)

    # Verify config was parsed
    assert plugin.gpio_pin == 21
    assert plugin.inverted is True
```

### 4. Hardware Interaction Testing

```python
async def test_gpio_output(mock_rpi_gpio):
    """Test GPIO output is correct."""
    plugin = await plugin_harness.load_plugin(PluginClass, "id", props)

    await plugin.on()
    await asyncio.sleep(0.1)

    # Verify GPIO state via mock
    assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH
```

### 5. Integration with cbpi4 Testing

```python
async def test_cbpi_integration(plugin_harness):
    """Test integration with cbpi4 APIs."""
    plugin = await plugin_harness.load_plugin(PluginClass, "id", props)

    # Test actor integration
    await plugin.on()
    state = await plugin_harness.cbpi.actor.get_state("id")
    assert state is True

    # Test sensor integration
    await plugin_harness.cbpi.sensor.set_value("temp", 65.5)
    value = await plugin_harness.cbpi.sensor.get_value("temp")
    assert value == 65.5
```

### 6. Error Handling Testing

```python
async def test_invalid_config():
    """Test handling of invalid configuration."""
    props = {
        "GPIO": "invalid",  # Invalid value
    }

    try:
        plugin = await plugin_harness.load_plugin(PluginClass, "id", props)
        # Plugin loaded - check error handling
        await plugin.on()
    except (ValueError, KeyError) as e:
        # Plugin correctly rejected invalid config
        pass
```

### 7. Cleanup Testing

```python
async def test_cleanup(mock_rpi_gpio):
    """Test proper cleanup on stop."""
    plugin = await plugin_harness.load_plugin(PluginClass, "id", props)

    await plugin.on()
    assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.HIGH

    # Stop plugin
    if hasattr(plugin, 'on_stop'):
        await plugin.on_stop()

    # Verify cleanup
    assert mock_rpi_gpio._pin_states.get(18) == mock_rpi_gpio.LOW
```

## Coverage Goals

### Target Coverage Before Refactoring

| Plugin | Lines | Target Coverage |
|--------|-------|-----------------|
| cbpi4-GPIOInput | 68 | 70%+ |
| cbpi4-AlwaysONGPIO | 46 | 80%+ |
| cbpi4-7SegDisplay | 323 | 60%+ |
| cbpi4-LCDisplay | 471 | 60%+ |
| cbpi4-i2cTempSensor | 91 | 70%+ |
| cbpi4-BMT-Key | 102 | 60%+ |
| cbpi4-BMT-MomentaryButtons | 105 | 60%+ |
| cbpi4-NOR3 | 30 | 80%+ |
| cbpi4-OneAtATime | 73 | 70%+ |
| cbpi4-InternetConnectedGPIO | 76 | 70%+ |

### Checking Coverage

```bash
# Generate coverage report
python3 -m pytest tests/real_plugin/ \
    --cov=cbpi4-GPIOInput/cbpi4-GPIOInput \
    --cov=cbpi4-AlwaysONGPIO/cbpi4-AlwaysONGPIO \
    --cov-report=html \
    --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

## Tips and Best Practices

### 1. Test Real Code, Not Mocks

❌ **Wrong:**
```python
class MockMyPlugin:  # Creating a mock
    def __init__(self, cbpi):
        self.cbpi = cbpi
```

✅ **Right:**
```python
@pytest.fixture
def real_plugin_class(plugin_loader):
    return plugin_loader("MyPlugin", "MyPlugin")  # Load real code
```

### 2. Mock Hardware, Not Business Logic

✅ **Mock:** RPi.GPIO, SMBus, Adafruit libraries, I2C devices
❌ **Don't Mock:** cbpi4 APIs (use MockCBPi), plugin logic

### 3. Use Async Sleep for Background Tasks

```python
# Load plugin that starts background task
plugin = await plugin_harness.load_plugin(...)

# Give background task time to run
await asyncio.sleep(1.0)

# Now test the effects
```

### 4. Clean Up After Tests

```python
@pytest_asyncio.fixture
async def my_plugin(plugin_harness, real_plugin_class):
    plugin = await plugin_harness.load_plugin(...)
    yield plugin
    # Cleanup happens automatically via plugin_harness
```

### 5. Document Actual Behavior

Some tests document how the plugin *actually* behaves, not necessarily how it *should* behave:

```python
async def test_invalid_config():
    """
    Test behavior with invalid config.

    Current behavior: Plugin raises ValueError
    TODO: Should probably use default value instead
    """
    try:
        plugin = await plugin_harness.load_plugin(...)
    except ValueError:
        pass  # Documented current behavior
```

## Troubleshooting

### Import Errors

**Error:** `ImportError: Failed to import PluginClass from cbpi4-Plugin`

**Solution:** Check that:
1. Plugin directory exists: `cbpi4-Plugin/cbpi4-Plugin/__init__.py`
2. Class name is correct
3. Plugin has no syntax errors

### Hardware Mock Not Working

**Error:** `AttributeError: module 'RPi.GPIO' has no attribute 'setup'`

**Solution:** Ensure `mock_rpi_gpio` fixture is used (should be auto-applied)

### Plugin Won't Load

**Error:** Plugin loads but doesn't work

**Solution:**
1. Check hardware mocks are configured
2. Verify configuration format
3. Add logging to see what plugin is doing
4. Compare with working examples

### Coverage is 0%

**Problem:** Coverage report shows 0% for plugin code

**Solution:** Check coverage command includes correct path:
```bash
--cov=cbpi4-YourPlugin/cbpi4-YourPlugin
```

## Next Steps

### For Each Plugin, Create:

1. **Initialization test** - Verify plugin loads
2. **Core functionality test** - Test main features
3. **Configuration test** - Test config parsing
4. **Hardware interaction test** - Test GPIO/I2C/etc
5. **Error handling test** - Test edge cases
6. **Cleanup test** - Test proper shutdown

### Coverage Milestone Strategy

**Phase 1: Core Plugins (Week 1)**
- ✅ AlwaysONGPIO (simple, good example)
- ✅ GPIOInput (actor pattern)
- ✅ 7SegDisplay (extension with I2C)
- Target: 40-50% coverage

**Phase 2: Remaining Plugins (Week 2)**
- OneAtATime
- NOR3
- i2cTempSensor
- InternetConnectedGPIO
- LCDisplay
- Target: 60-70% coverage

**Phase 3: Complex Plugins (Week 3)**
- BMT-Key
- BMT-MomentaryButtons
- Target: 60-70% coverage overall

**Phase 4: Refactoring (Week 4+)**
- Use tests to ensure refactoring doesn't break functionality
- Add tests for new unified interface
- Maintain >60% coverage throughout

## Resources

- **Mock Framework:** `tests/fixtures/cbpi_mock.py`
- **Hardware Mocks:** `tests/fixtures/hardware_mocks.py`
- **Test Data:** `tests/fixtures/test_data.py`
- **Example Tests:** Files in this directory

## Contributing

When adding new real plugin tests:

1. Follow the naming pattern: `test_real_<plugin_name>.py`
2. Add `pytestmark = [pytest.mark.real_plugin, ...]`
3. Use `plugin_loader` fixture to load real plugin
4. Mock hardware, not business logic
5. Document actual behavior, especially edge cases
6. Aim for 60-70% coverage minimum
