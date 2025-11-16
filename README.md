# Brewmotron Brewing Automation Software

A comprehensive beer brewing automation system built on CraftBeerPi4, providing complete control over temperature monitoring, heating elements, pumps, and user interface displays for automated brewing processes.

**⚠️ Project Status**: This is a personal hobby project created as a learning tool for coding patterns, approaches, and the CraftBeerPi4 API. The code has been used successfully for 10+ brews but contains coding issues that are being improved over time. No guarantees are provided for functionality, and the current structure is not designed to support community contributions.

## Overview

Brewmotron consists of 10 CraftBeerPi4 plugins working together to provide:

- **Temperature Control**: Multi-zone temperature monitoring and heating control for mash tun, sparge water, and boiler
- **Hardware Interface**: GPIO control for pumps, heaters, LEDs, and buttons
- **Display Systems**: 7-segment displays and LCD screens showing real-time brewing data
- **Mode Management**: Key-based switching between brewing, fermentation, and cleaning modes
- **Safety Features**: One-at-a-time actor coordination to prevent equipment conflicts

## Hardware Requirements

### Core Components
- Raspberry Pi (with GPIO access)
- I2C-enabled 7-segment displays (addresses 0x70-0x76)
- ADS1115 analog-to-digital converter
- Temperature probes (analog)
- GPIO-controlled relays for heaters and pumps

### I2C Device Map
- **0x70**: Sparge temperature display
- **0x71**: Boiler temperature display  
- **0x72**: Mash temperature display
- **0x74**: Sparge target temperature display
- **0x75**: Boiler target temperature display
- **0x76**: Mash target temperature display

### GPIO Assignments
GPIO pin assignments are configured through the CraftBeerPi4 web interface and plugin configuration:
- LEDs (status indicators)
- Pumps (sparge, boiler)
- Heater relays
- Control buttons and mode switches

## Installation

### Prerequisites
```bash
# Enable I2C on Raspberry Pi
sudo raspi-config
# Navigate to Interfacing Options > I2C > Enable

# Install CraftBeerPi4
pip install cbpi4
```

### Plugin Installation
Each plugin can be installed individually:

```bash
# Install via pip (recommended)
sudo pip3 install cbpi4-7SegDisplay
sudo cbpi add cbpi4-7SegDisplay

# Repeat for other plugins:
# cbpi4-LCDisplay, cbpi4-i2cTempSensor, cbpi4-GPIOInput
# cbpi4-AlwaysONGPIO, cbpi4-BMT-Key, cbpi4-BMT-MomentaryButtons
# cbpi4-InternetConnectedGPIO, cbpi4-OneAtATime, cbpi4-NOR3
```

### Development Installation
```bash
# For plugin development
sudo cbpi create <plugin-name>
sudo pip3 install -e ./<plugin-name>
```

## Plugin Architecture

### Core Plugins

#### cbpi4-7SegDisplay
7-segment display management for real-time temperature display during brewing.

#### cbpi4-LCDisplay  
LCD display with multiple modes:
- **Multidisplay**: Cycles through all kettles showing target/current temps
- **Single**: Displays one kettle with faster updates
- **Sensor**: Shows sensor values and names
- **Default**: Shows system info when not brewing

#### cbpi4-i2cTempSensor
I2C temperature sensor interface for brewing vessel monitoring.

#### cbpi4-BMT-Key
Mode switching functionality:
- **Brew Mode**: Normal brewing operations
- **Ferment Mode**: Fermentation control
- **Clean Mode**: Cleaning cycle operations

#### cbpi4-OneAtATime
Actor coordination ensuring only one heating element operates at a time to prevent electrical overload.

### Hardware Interface Plugins

#### cbpi4-GPIOInput / cbpi4-BMT-MomentaryButtons
Handle physical button inputs for temperature adjustment and system control.

#### cbpi4-AlwaysONGPIO / cbpi4-InternetConnectedGPIO
GPIO output management for pumps, heaters, and status indicators.

#### cbpi4-NOR3
Logic gate functionality for complex brewing control sequences.

## Configuration

### CraftBeerPi4 Configuration
Main configuration files located in `craftbeerpi/config/`:
- `config.yaml`: Main system configuration
- `actor.json`: Actor (relay/pump) definitions  
- `sensor.json`: Temperature sensor configurations
- `kettle.json`: Brewing vessel definitions

### Display Configuration
Each display plugin has configurable parameters:
- **I2C Address**: Hardware address of display device
- **Character Map**: A00/A02 for different LCD character sets
- **Display Mode**: Multidisplay/Single/Sensor modes
- **Refresh Rate**: Update frequency for display cycling

## Brewing Process

**Operational Status**: The system has been successfully used for 10+ brewing sessions. UI tuning and workflow optimizations are ongoing as usage patterns are refined.

1. **Setup**: Configure vessels, sensors, and actors through CraftBeerPi4 web interface
2. **Recipe**: Load or create brewing recipe with temperature steps and timing
3. **Mode Selection**: Use physical key switch to select brewing mode
4. **Monitoring**: Real-time temperature display on 7-segment displays and LCD
5. **Control**: Automatic heating control with manual override capabilities

## Known Issues & Future Development

### Current Limitations
- Performance issues due to excessive state polling across plugins (~327 API calls/minute)
- I2C bus contention from uncoordinated device access
- Lack of centralized configuration management
- Synchronous blocking calls in async contexts

### Planned Improvements

#### Cache Handler Architecture (Recommended - In Development)
A comprehensive data access optimization proposal is documented in `CBPI4_DATA_ACCESS_ARCHITECTURE.md`:
- **94% reduction** in API calls through intelligent caching
- **Event-driven updates** replacing polling (1-6s latency → <100ms)
- **I2C coordination** eliminating bus conflicts
- **Async-first design** for non-blocking data access
- See `CBPI4_DATA_ACCESS_ARCHITECTURE.md` for detailed architecture diagrams
- See `DEPLOYMENT_STEPS.md` for phased implementation plan and progress tracking

**Development Status**: Implementation in progress on feature branch `claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB`. Main branch remains stable for production use. Deployment to main will occur after complete validation (estimated 5-7 weeks).

#### Alternative Refactor Plan
A comprehensive refactor is documented in `BREWMOTRON_REFACTOR_PLAN.md` to:
- Consolidate plugins into coordinated monolithic architecture
- Implement centralized I2C and state management
- Maintain modularity for future development
- ⚠️ Note: Cache handler approach is recommended as a less disruptive alternative

**⚠️ Testing Infrastructure Status** - Comprehensive automated testing framework operational with hardware mocking capabilities. Integration tests have known failures requiring resolution.

## Development

### File Structure
```
├── cbpi4-*/                           # Individual CraftBeerPi4 plugins
├── tests/                             # Comprehensive testing infrastructure
│   ├── unit/                         # Unit tests for individual plugins
│   ├── integration/                  # Integration tests
│   ├── fixtures/                     # Test fixtures and mocks
│   └── conftest.py                   # Global test configuration
├── .github/workflows/                # CI/CD pipeline configuration
├── CBPI4_DATA_ACCESS_ARCHITECTURE.md # Data access optimization proposal
├── DEPLOYMENT_STEPS.md               # Cache handler implementation roadmap
├── RASPBERRYPI_SETUP.md              # Hardware setup guide
├── requirements-test.txt             # Testing dependencies
├── run_tests.py                      # Test runner script
├── pytest.ini                        # Test configuration
└── README.md
```

### Testing Infrastructure

⚠️ **IMPORTANT: AI-Generated Testing Disclaimer**
All unit and integration tests in this project are AI-generated by Claude Code (claude.ai/code) and have NOT been reviewed by humans. Manual verification and validation by qualified developers is REQUIRED before production use. Tests serve as starting points requiring human validation - passing tests indicate execution success, not human-verified quality.

**⚠️ MIXED TESTING RESULTS**: Comprehensive testing infrastructure operational - integration tests have known issues.

#### Testing Achievement Summary
- **128 tests** covering **7+ plugins** (814% increase from previous 14 tests)
  - **89 unit tests** in `tests/unit/`
  - **39 integration tests** in `tests/integration/`
- **Integration tests have known failures** - Some test failures remain to be addressed
- Comprehensive mock frameworks for GPIO, I2C, displays, and temperature sensors
- GitHub Actions CI/CD pipeline with automated testing
- Coverage reporting with HTML output
- **Reliable test execution** in seconds with proper timeout protection
- ⚠️ **All tests are AI-generated** by Claude Code and require manual verification

#### Quick Test Commands
```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests with coverage
python run_tests.py all

# Run specific test types
python run_tests.py unit          # Unit tests only
python run_tests.py hardware      # Hardware simulation tests
python run_tests.py integration   # Integration tests

# Generate comprehensive test report
python run_tests.py report
```

#### Test Architecture
1. **Unit Tests** (`tests/unit/`) - Individual plugin components in isolation
2. **Integration Tests** (`tests/integration/`) - Plugin interactions with CraftBeerPi4 framework
3. **Hardware Simulation Tests** - Hardware interface logic with realistic device simulation
4. **CI/CD Pipeline** - Automated testing with GitHub Actions

#### Stability Improvements
- **Fixed AsyncIO deadlocks** in actor coordination testing
- **Enhanced test cleanup** with proper async task cancellation
- **Added timeout protection** to prevent infinite waits
- **Improved mock framework** async task lifecycle management
- **Comprehensive error handling** and logging

#### Hardware Mocking Capabilities
- **GPIO Simulation**: Pin state tracking, interrupt simulation, electrical behavior
- **I2C Device Simulation**: Realistic device register behavior, bus contention detection
- **Temperature Sensor Simulation**: Realistic temperature curves, noise, drift, and failure modes
- **Display Testing**: 7-segment and LCD display state verification

#### Coverage Targets
- Unit Tests: 80%+ line coverage minimum
- Integration Tests: 70%+ line coverage minimum
- Overall Project: 75%+ line coverage minimum

### Development Guidelines

**Important**: This is currently a personal learning project and is not structured to support community contributions. The codebase contains various coding issues and patterns that are being improved as development continues.

If modifying for personal use:
1. Follow existing CraftBeerPi4 plugin structure
2. **Run the stable test suite** before making hardware deployments: `python run_tests.py all`
3. Test I2C address conflicts before deployment
4. Verify GPIO assignments don't conflict with existing hardware
5. Update configuration documentation for new parameters
6. **Add tests for new functionality** using the robust test framework patterns
7. Expect to encounter and fix coding issues as you work with the system

#### Testing New Code

⚠️ **CRITICAL: Human Review Required**
All testing infrastructure is AI-generated. Human review and validation is REQUIRED before relying on test results for production deployments.

When adding new plugins or functionality:
1. Create unit tests in `tests/unit/test_your_plugin.py`
2. Use the provided hardware mocks from `tests/fixtures/`
3. Follow the stable async testing patterns in existing tests
4. **MANUALLY VERIFY** all test logic before hardware deployment
5. **Human validation required** for all AI-generated test patterns
6. Ensure tests pass AND have been human-reviewed before production use

## System Requirements

**Hardware Compatibility**: All plugins are designed specifically for Brewmotron hardware but are structured to be reusable independently for other CraftBeerPi4 systems with appropriate hardware modifications.

**Software Dependencies**: 
- CraftBeerPi4 framework
- Python 3.7+
- I2C libraries (smbus2, adafruit-circuitpython-*)
- GPIO libraries (RPi.GPIO)

## License

Individual plugins may have different licenses. Check each plugin directory for specific license information.

## Support

⚠️ **Testing Support Notice**: All automated tests are AI-generated and require human verification. Test results should be validated manually before making production decisions.

For technical issues:
- **Run the test suite with caution**: `python run_tests.py all` - results require human verification
- Check CraftBeerPi4 web interface for configuration errors
- Verify I2C device connectivity: `sudo i2cdetect -y 1`
- Confirm GPIO permissions and hardware connections
- Review individual plugin documentation for specific troubleshooting
- **Test environment setup**: `python run_tests.py check` to verify testing dependencies
- **Manual validation required** for all automated test results

## Hardware Build Information

**Note**: This repository contains only the software components of the Brewmotron system. The physical hardware build, including PCB designs, wiring diagrams, component specifications, and assembly instructions, is maintained separately. If you're interested in building the complete Brewmotron hardware system, please reach out directly for access to the hardware documentation and build guides.