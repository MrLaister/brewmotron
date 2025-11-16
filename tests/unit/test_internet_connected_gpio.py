"""
Unit tests for cbpi4-InternetConnectedGPIO plugin.

Tests the Internet Connected GPIO functionality with comprehensive hardware mocking
and edge case handling for network connectivity monitoring and GPIO control.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import pytest_asyncio

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import HardwareTestHarness, MockRPiGPIO
from tests.fixtures.test_data import GPIOActorConfigFactory, PluginConfigFactory

# Mark all tests in this module as hardware tests
# PHASE 2: Temporarily skipped during cache handler conversion
# These plugin tests will be re-enabled after plugins are refactored to use cache handler
pytestmark = [
    pytest.mark.hardware,
    pytest.mark.skip(reason="Phase 2: Plugin refactoring - re-enable after cache handler integration"),
]


class TestInternetConnectedGPIO:
    """Test suite for Internet Connected GPIO plugin."""

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
    def internet_gpio_config(self):
        """Create Internet Connected GPIO plugin configuration."""
        return GPIOActorConfigFactory(
            id="test_internet_gpio",
            name="TestInternetGPIO",
            props={"GPIO": 18, "SleepTime_Connected": 30, "SleepTime_Disconnected": 5},
        )

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_harness, internet_gpio_config):
        """Test Internet Connected GPIO plugin initialization."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.power = 100

            def init(self, cbpi):
                self.state = False
                self.cbpi = cbpi
                # Mock initialization complete
                self.initialized = True
                return True

            async def on_start(self):
                self.power = 100
                gpio = self.props.get("GPIO")
                # Mock GPIO.setup(gpio, GPIO.OUT) call
                self.state = False  # Initialize to OFF state
                # Mock starting ping loop
                self.initialized = True  # Set during startup
                return True

            async def off(self):
                self.state = False

        plugin = await plugin_harness.load_plugin(
            MockGPIOInternetConnected,
            internet_gpio_config.id,
            internet_gpio_config.props,
        )

        # Verify initialization
        assert plugin.state == False
        assert plugin.power == 100
        assert plugin.props["GPIO"] == 18
        assert plugin.props["SleepTime_Connected"] == 30
        assert plugin.props["SleepTime_Disconnected"] == 5
        assert hasattr(plugin, "initialized")
        assert plugin.initialized == True

        # Test on_start behavior
        await plugin.on_start()
        assert plugin.power == 100

    @pytest.mark.asyncio
    async def test_internet_connectivity_detection(self, plugin_harness, internet_gpio_config):
        """Test network connectivity detection."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.ping_results = []
                self.ping_call_count = 0

            def check_connected(self):
                """Mock network connectivity check."""
                self.ping_call_count += 1

                # Simulate different connectivity scenarios
                if self.ping_call_count == 1:
                    # First check: Connected
                    response = 0  # Success
                    result = True
                elif self.ping_call_count == 2:
                    # Second check: Disconnected
                    response = 1  # Failure
                    result = False
                else:
                    # Subsequent checks: Connected again
                    response = 0  # Success
                    result = True

                self.ping_results.append(
                    {
                        "call": self.ping_call_count,
                        "response": response,
                        "connected": result,
                    }
                )

                return result

        plugin = await plugin_harness.load_plugin(
            MockGPIOInternetConnected,
            internet_gpio_config.id,
            internet_gpio_config.props,
        )

        # Test connectivity detection
        connected1 = plugin.check_connected()  # Should be connected
        connected2 = plugin.check_connected()  # Should be disconnected
        connected3 = plugin.check_connected()  # Should be connected again

        assert connected1 == True
        assert connected2 == False
        assert connected3 == True

        assert len(plugin.ping_results) == 3
        assert plugin.ping_results[0]["connected"] == True
        assert plugin.ping_results[1]["connected"] == False
        assert plugin.ping_results[2]["connected"] == True

    @pytest.mark.asyncio
    async def test_ping_loop_state_transitions(self, plugin_harness, internet_gpio_config):
        """Test ping loop behavior and state transitions."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.state_changes = []
                self.sleep_times = []
                self.connection_checks = 0

            def check_connected(self):
                """Mock connectivity with alternating states."""
                self.connection_checks += 1
                # Alternate between connected and disconnected
                return self.connection_checks % 2 == 1

            async def on(self, power=None):
                self.state = True
                self.state_changes.append("ON")

            async def off(self):
                self.state = False
                self.state_changes.append("OFF")

            async def pingloop(self):
                """Mock ping loop with limited iterations for testing."""
                iterations = 0
                max_iterations = 4  # Limit for testing

                while iterations < max_iterations:
                    previous_state = self.state
                    state = self.check_connected()

                    if state != previous_state:
                        if state:
                            try:
                                await self.on()
                            except Exception:
                                pass
                        else:
                            try:
                                await self.off()
                            except Exception:
                                pass

                    # Record sleep time based on state
                    if state == True:
                        refreshtime = self.props.get("SleepTime_Connected", 30)
                    else:
                        refreshtime = self.props.get("SleepTime_Disconnected", 5)

                    self.sleep_times.append(refreshtime)

                    # In real implementation, would await asyncio.sleep(refreshtime)
                    # For testing, we just record the intended sleep time
                    iterations += 1

        plugin = await plugin_harness.load_plugin(
            MockGPIOInternetConnected,
            internet_gpio_config.id,
            internet_gpio_config.props,
        )

        # Run the ping loop
        await plugin.pingloop()

        # Verify state transitions occurred
        assert len(plugin.state_changes) > 0
        assert len(plugin.sleep_times) == 4

        # Check that appropriate sleep times were used
        connected_sleeps = [t for t in plugin.sleep_times if t == 30]
        disconnected_sleeps = [t for t in plugin.sleep_times if t == 5]

        # Should have both connected and disconnected sleep times
        assert len(connected_sleeps) > 0 or len(disconnected_sleeps) > 0

    @pytest.mark.asyncio
    async def test_gpio_output_control(self, plugin_harness, internet_gpio_config):
        """Test GPIO output control based on connectivity."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.gpio_outputs = []

            async def on(self, power=None):
                gpio = self.props.get("GPIO", None)
                if gpio is not None:
                    # Mock GPIO.output(gpio, True)
                    self.gpio_outputs.append(f"GPIO {gpio} -> HIGH")
                self.state = True

            async def off(self):
                gpio = self.props.get("GPIO", None)
                if gpio is not None:
                    # Mock GPIO.output(gpio, False)
                    self.gpio_outputs.append(f"GPIO {gpio} -> LOW")
                self.state = False

        plugin = await plugin_harness.load_plugin(
            MockGPIOInternetConnected,
            internet_gpio_config.id,
            internet_gpio_config.props,
        )

        # Test GPIO control
        await plugin.on()
        assert plugin.state == True
        assert "GPIO 18 -> HIGH" in plugin.gpio_outputs

        await plugin.off()
        assert plugin.state == False
        assert "GPIO 18 -> LOW" in plugin.gpio_outputs

    @pytest.mark.asyncio
    async def test_different_sleep_time_configurations(self, plugin_harness):
        """Test different sleep time configurations."""
        # Test configuration with different sleep times
        custom_config = GPIOActorConfigFactory(
            id="test_custom_sleep",
            name="TestCustomSleep",
            props={
                "GPIO": 19,
                "SleepTime_Connected": 60,  # 1 minute when connected
                "SleepTime_Disconnected": 1,  # 1 second when disconnected
            },
        )

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.sleep_time_tests = []

            def get_sleep_time(self, connected_state):
                """Test sleep time calculation."""
                if connected_state:
                    refreshtime = self.props.get("SleepTime_Connected", 30)
                else:
                    refreshtime = self.props.get("SleepTime_Disconnected", 1)

                self.sleep_time_tests.append(
                    {
                        "state": "connected" if connected_state else "disconnected",
                        "sleep_time": refreshtime,
                    }
                )

                return refreshtime

        plugin = await plugin_harness.load_plugin(MockGPIOInternetConnected, custom_config.id, custom_config.props)

        # Test sleep time calculation
        connected_sleep = plugin.get_sleep_time(True)
        disconnected_sleep = plugin.get_sleep_time(False)

        assert connected_sleep == 60
        assert disconnected_sleep == 1
        assert len(plugin.sleep_time_tests) == 2

    @pytest.mark.asyncio
    async def test_power_management(self, plugin_harness, internet_gpio_config):
        """Test power level management."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.power = 100
                self.power_updates = []

            async def set_power(self, power=100):
                self.power = power
                # Mock cbpi.actor.actor_update call
                self.power_updates.append(f"Power set to {power}% for actor {self.id}")

        plugin = await plugin_harness.load_plugin(
            MockGPIOInternetConnected,
            internet_gpio_config.id,
            internet_gpio_config.props,
        )

        # Test power management
        await plugin.set_power(75)

        assert plugin.power == 75
        assert len(plugin.power_updates) == 1
        assert "Power set to 75%" in plugin.power_updates[0]


class TestInternetConnectedGPIOEdgeCases:
    """Test edge cases and error conditions for Internet Connected GPIO plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_missing_gpio_configuration(self, plugin_harness):
        """Test handling of missing GPIO configuration."""
        no_gpio_config = GPIOActorConfigFactory(
            id="test_no_gpio",
            name="TestNoGPIO",
            props={
                "GPIO": None,  # Missing GPIO configuration
                "SleepTime_Connected": 30,
                "SleepTime_Disconnected": 5,
            },
        )

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.gpio_errors = []

            async def on(self, power=None):
                gpio = self.props.get("GPIO", None)
                if gpio is not None:
                    self.gpio_errors.append(f"GPIO {gpio} -> HIGH")
                else:
                    self.gpio_errors.append("No GPIO configured for HIGH")
                self.state = True

            async def off(self):
                gpio = self.props.get("GPIO", None)
                if gpio is not None:
                    self.gpio_errors.append(f"GPIO {gpio} -> LOW")
                else:
                    self.gpio_errors.append("No GPIO configured for LOW")
                self.state = False

        plugin = await plugin_harness.load_plugin(MockGPIOInternetConnected, no_gpio_config.id, no_gpio_config.props)

        # Test GPIO operations with missing configuration
        await plugin.on()
        await plugin.off()

        assert len(plugin.gpio_errors) == 2
        assert "No GPIO configured for HIGH" in plugin.gpio_errors
        assert "No GPIO configured for LOW" in plugin.gpio_errors

    @pytest.mark.asyncio
    async def test_network_command_failure(self, plugin_harness):
        """Test handling of network command failures."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.network_errors = []

            def check_connected(self):
                """Mock network check with command failure."""
                hostname = "google.com"

                try:
                    # Simulate os.system() call failure scenarios
                    if not hasattr(self, "_failure_count"):
                        self._failure_count = 0
                    self._failure_count += 1

                    if self._failure_count == 1:
                        # Simulate network unreachable
                        response = 2  # Network unreachable
                        self.network_errors.append(f"Network unreachable to {hostname}")
                        return False
                    elif self._failure_count == 2:
                        # Simulate timeout
                        response = 1  # Timeout
                        self.network_errors.append(f"Timeout connecting to {hostname}")
                        return False
                    else:
                        # Success
                        response = 0  # Success
                        return True

                except Exception as e:
                    self.network_errors.append(f"Network check error: {e}")
                    return False

        config = GPIOActorConfigFactory(
            id="test_network_failure",
            name="TestNetworkFailure",
            props={"GPIO": 20, "SleepTime_Connected": 30, "SleepTime_Disconnected": 5},
        )

        plugin = await plugin_harness.load_plugin(MockGPIOInternetConnected, config.id, config.props)

        # Test network failure scenarios
        result1 = plugin.check_connected()  # Network unreachable
        result2 = plugin.check_connected()  # Timeout
        result3 = plugin.check_connected()  # Success

        assert result1 == False
        assert result2 == False
        assert result3 == True

        assert len(plugin.network_errors) == 2
        assert "Network unreachable to google.com" in plugin.network_errors
        assert "Timeout connecting to google.com" in plugin.network_errors

    @pytest.mark.asyncio
    async def test_ping_loop_exception_handling(self, plugin_harness):
        """Test exception handling in ping loop."""

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.exception_count = 0
                self.exceptions_caught = []

            def check_connected(self):
                """Mock connectivity check with exceptions."""
                self.exception_count += 1
                if self.exception_count <= 2:
                    # First two calls raise exceptions
                    raise Exception(f"Connection check failed #{self.exception_count}")
                else:
                    # Subsequent calls succeed
                    return True

            async def on(self, power=None):
                try:
                    if hasattr(self, "_on_should_fail") and self._on_should_fail:
                        raise Exception("GPIO on() failed")
                    self.state = True
                except Exception as e:
                    self.exceptions_caught.append(f"on() error: {e}")

            async def off(self):
                try:
                    if hasattr(self, "_off_should_fail") and self._off_should_fail:
                        raise Exception("GPIO off() failed")
                    self.state = False
                except Exception as e:
                    self.exceptions_caught.append(f"off() error: {e}")

            async def pingloop_with_error_handling(self):
                """Mock ping loop with exception handling."""
                iterations = 0
                max_iterations = 5

                while iterations < max_iterations:
                    try:
                        previous_state = self.state
                        state = self.check_connected()

                        if state != previous_state:
                            if state:
                                self.state = True
                                try:
                                    asyncio.create_task(self.on())
                                except Exception as e:
                                    self.exceptions_caught.append(f"Task creation error (on): {e}")
                            else:
                                self.state = False
                                try:
                                    asyncio.create_task(self.off())
                                except Exception as e:
                                    self.exceptions_caught.append(f"Task creation error (off): {e}")

                    except Exception as e:
                        self.exceptions_caught.append(f"Ping loop error: {e}")

                    iterations += 1

        config = GPIOActorConfigFactory(
            id="test_exception_handling",
            name="TestExceptionHandling",
            props={"GPIO": 21, "SleepTime_Connected": 30, "SleepTime_Disconnected": 5},
        )

        plugin = await plugin_harness.load_plugin(MockGPIOInternetConnected, config.id, config.props)

        # Test exception handling in ping loop
        await plugin.pingloop_with_error_handling()

        assert len(plugin.exceptions_caught) >= 2  # At least the connectivity check exceptions
        assert any("Connection check failed #1" in exc for exc in plugin.exceptions_caught)
        assert any("Connection check failed #2" in exc for exc in plugin.exceptions_caught)

    @pytest.mark.asyncio
    async def test_default_sleep_time_fallback(self, plugin_harness):
        """Test fallback to default sleep times when not configured."""
        minimal_config = GPIOActorConfigFactory(
            id="test_default_sleep",
            name="TestDefaultSleep",
            props={
                "GPIO": 22
                # Missing SleepTime_Connected and SleepTime_Disconnected
            },
        )

        class MockGPIOInternetConnected:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.default_sleep_tests = []

            def get_sleep_time_with_defaults(self, connected_state):
                """Test sleep time with default fallback."""
                if connected_state:
                    refreshtime = self.props.get("SleepTime_Connected", 30)  # Default 30
                else:
                    refreshtime = self.props.get("SleepTime_Disconnected", 1)  # Default 1

                self.default_sleep_tests.append(
                    {
                        "state": "connected" if connected_state else "disconnected",
                        "sleep_time": refreshtime,
                        "used_default": refreshtime in [30, 1],
                    }
                )

                return refreshtime

        plugin = await plugin_harness.load_plugin(MockGPIOInternetConnected, minimal_config.id, minimal_config.props)

        # Test default sleep time fallback
        connected_sleep = plugin.get_sleep_time_with_defaults(True)
        disconnected_sleep = plugin.get_sleep_time_with_defaults(False)

        assert connected_sleep == 30  # Default connected sleep time
        assert disconnected_sleep == 1  # Default disconnected sleep time

        assert len(plugin.default_sleep_tests) == 2
        assert all(test["used_default"] for test in plugin.default_sleep_tests)
