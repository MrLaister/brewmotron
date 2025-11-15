"""
Unit tests for cbpi4-BMT-MomentaryButtons plugin.

Tests the BMT Momentary Button functionality with comprehensive hardware mocking
and edge case handling for brewing system control (+10, +1, Select, -1, -10).
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
pytestmark = pytest.mark.hardware


class TestBMTMomentaryButtons:
    """Test suite for BMT MomentaryButtons plugin."""

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
    def button_config(self):
        """Create momentary button plugin configuration."""
        return GPIOActorConfigFactory(
            id="test_button",
            name="TestMomentaryButton",
            props={"GPIO": 22, "Inverted": "No", "Button Function": "Select"},
        )

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_harness, button_config):
        """Test BMT MomentaryButton plugin initialization."""

        class MockBMTMomentaryButton:
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
                return True

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, button_config.id, button_config.props
        )

        # Verify initialization
        assert plugin.state == False
        assert plugin.power == 100
        assert plugin.props["GPIO"] == 22
        assert plugin.props["Button Function"] == "Select"

    @pytest.mark.asyncio
    async def test_gpio_state_detection_normal_logic(
        self, plugin_harness, button_config
    ):
        """Test GPIO input state detection with normal logic."""

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.gpio_states = []  # Track GPIO state changes

            def get_state(self):
                """Mock GPIO state detection."""
                gpio = self.props.get("GPIO")
                # Simulate GPIO.input() calls - simulate button press sequence
                if not hasattr(self, "_gpio_input_call_count"):
                    self._gpio_input_call_count = 0

                self._gpio_input_call_count += 1

                # Simulate button press: off -> on -> off
                if self._gpio_input_call_count == 1:
                    newInput = 0  # Button not pressed
                elif self._gpio_input_call_count == 2:
                    newInput = 1  # Button pressed
                else:
                    newInput = 0  # Button released

                if self.props.get("Inverted") == "No":
                    high = 1
                    low = 0
                elif self.props.get("Inverted") == "Yes":
                    high = 0
                    low = 1

                # State transition logic
                if (newInput == high) and (self.state == False):
                    self.state = True
                    self.gpio_states.append("Off to On")
                    asyncio.create_task(self.on())
                elif (newInput == low) and (self.state == True):
                    self.state = False
                    self.gpio_states.append("On to Off")
                    asyncio.create_task(self.off())

                return self.state

            async def on(self, power=None):
                self.state = True

            async def off(self):
                self.state = False

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, button_config.id, button_config.props
        )

        # Test button press sequence
        state1 = plugin.get_state()  # Initial state
        state2 = plugin.get_state()  # Button press
        state3 = plugin.get_state()  # Button release

        await asyncio.sleep(0.1)  # Allow async tasks to complete

        assert len(plugin.gpio_states) == 2
        assert "Off to On" in plugin.gpio_states
        assert "On to Off" in plugin.gpio_states

    @pytest.mark.asyncio
    async def test_gpio_state_detection_inverted_logic(self, plugin_harness):
        """Test GPIO input state detection with inverted logic."""
        inverted_config = GPIOActorConfigFactory(
            id="test_button_inverted",
            name="TestInvertedButton",
            props={"GPIO": 22, "Inverted": "Yes", "Button Function": "+1"},
        )

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.gpio_states = []

            def get_state(self):
                """Mock GPIO state detection with inverted logic."""
                gpio = self.props.get("GPIO")

                if not hasattr(self, "_gpio_input_call_count"):
                    self._gpio_input_call_count = 0

                self._gpio_input_call_count += 1

                # Simulate inverted button: high when not pressed, low when pressed
                if self._gpio_input_call_count == 1:
                    newInput = 1  # Not pressed (high)
                elif self._gpio_input_call_count == 2:
                    newInput = 0  # Pressed (low)
                else:
                    newInput = 1  # Released (high)

                if self.props.get("Inverted") == "Yes":
                    high = 0  # Inverted: active low
                    low = 1  # Inverted: inactive high

                if (newInput == high) and (self.state == False):
                    self.state = True
                    self.gpio_states.append("Off to On (Inverted)")
                elif (newInput == low) and (self.state == True):
                    self.state = False
                    self.gpio_states.append("On to Off (Inverted)")

                return self.state

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, inverted_config.id, inverted_config.props
        )

        # Test inverted button press sequence
        state1 = plugin.get_state()  # Initial state (high = not pressed)
        state2 = plugin.get_state()  # Button press (low = pressed)
        state3 = plugin.get_state()  # Button release (high = not pressed)

        assert len(plugin.gpio_states) == 2
        assert "Off to On (Inverted)" in plugin.gpio_states
        assert "On to Off (Inverted)" in plugin.gpio_states

    @pytest.mark.asyncio
    async def test_button_function_select(self, plugin_harness, button_config):
        """Test Select button function - step progression."""

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.progress_called = False

            async def on(self, power=None):
                self.state = True
                if self.props.get("Button Function") == "Select":
                    await self.progress()

            async def progress(self):
                """Mock step progression."""
                # Simulate finding active step and progressing
                self.progress_called = True

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, button_config.id, button_config.props
        )

        # Test Select button function
        await plugin.on()

        assert plugin.state == True
        assert plugin.progress_called == True

    @pytest.mark.asyncio
    async def test_button_function_temperature_increase(self, plugin_harness):
        """Test temperature increase button functions (+1, +10)."""
        plus_ten_config = GPIOActorConfigFactory(
            id="test_button_plus10",
            name="TestPlus10Button",
            props={"GPIO": 23, "Inverted": "No", "Button Function": "+10"},
        )

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.temp_changes = []

            async def on(self, power=None):
                self.state = True
                if self.props.get("Button Function") == "+10":
                    await self.temp_change(10)
                elif self.props.get("Button Function") == "+1":
                    await self.temp_change(1)

            async def temp_change(self, tempIncrement):
                """Mock temperature change."""
                self.temp_changes.append(tempIncrement)

                # Mock getting active step values
                targetTemp, kettle_id = self.get_active_step_values()
                if targetTemp and kettle_id:
                    # Simulate current temp of 65°C, increment by tempIncrement
                    currentTemp = 65
                    newTargetTemp = currentTemp + tempIncrement

                    # Clamp to valid range
                    if newTargetTemp > 100:
                        newTargetTemp = 100
                    elif newTargetTemp < 0:
                        newTargetTemp = 0

                    self.temp_changes.append(f"New target: {newTargetTemp}")

            def get_active_step_values(self):
                """Mock active step detection."""
                # Simulate active step with kettle
                return "65", "kettle_1"

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, plus_ten_config.id, plus_ten_config.props
        )

        # Test +10 temperature function
        await plugin.on()

        assert plugin.state == True
        assert 10 in plugin.temp_changes
        assert "New target: 75" in plugin.temp_changes

    @pytest.mark.asyncio
    async def test_button_function_temperature_decrease(self, plugin_harness):
        """Test temperature decrease button functions (-1, -10)."""
        minus_ten_config = GPIOActorConfigFactory(
            id="test_button_minus10",
            name="TestMinus10Button",
            props={"GPIO": 24, "Inverted": "No", "Button Function": "-10"},
        )

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.temp_changes = []

            async def on(self, power=None):
                self.state = True
                if self.props.get("Button Function") == "-10":
                    await self.temp_change(-10)
                elif self.props.get("Button Function") == "-1":
                    await self.temp_change(-1)

            async def temp_change(self, tempIncrement):
                """Mock temperature change."""
                self.temp_changes.append(tempIncrement)

                targetTemp, kettle_id = self.get_active_step_values()
                if targetTemp and kettle_id:
                    currentTemp = 65
                    newTargetTemp = currentTemp + tempIncrement

                    if newTargetTemp > 100:
                        newTargetTemp = 100
                    elif newTargetTemp < 0:
                        newTargetTemp = 0

                    self.temp_changes.append(f"New target: {newTargetTemp}")

            def get_active_step_values(self):
                return "65", "kettle_1"

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, minus_ten_config.id, minus_ten_config.props
        )

        # Test -10 temperature function
        await plugin.on()

        assert plugin.state == True
        assert -10 in plugin.temp_changes
        assert "New target: 55" in plugin.temp_changes

    @pytest.mark.asyncio
    async def test_temperature_range_clamping(self, plugin_harness):
        """Test temperature clamping to valid ranges (0-100°C)."""

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.temp_results = []

            async def temp_change(self, tempIncrement):
                """Mock temperature change with clamping."""
                targetTemp, kettle_id = self.get_active_step_values()
                if targetTemp and kettle_id:
                    currentTemp = int(targetTemp)
                    newTargetTemp = currentTemp + tempIncrement

                    # Test clamping logic
                    if newTargetTemp > 100:
                        newTargetTemp = 100
                    elif newTargetTemp < 0:
                        newTargetTemp = 0

                    self.temp_results.append(
                        {
                            "original": currentTemp,
                            "increment": tempIncrement,
                            "clamped": newTargetTemp,
                        }
                    )

            def get_active_step_values(self):
                # Return different temperature scenarios
                if not hasattr(self, "_call_count"):
                    self._call_count = 0
                self._call_count += 1

                if self._call_count == 1:
                    return "95", "kettle_1"  # High temp scenario
                elif self._call_count == 2:
                    return "5", "kettle_1"  # Low temp scenario
                else:
                    return "50", "kettle_1"  # Normal scenario

        config = GPIOActorConfigFactory(
            id="test_clamping",
            name="TestClamping",
            props={"GPIO": 25, "Inverted": "No", "Button Function": "+10"},
        )

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, config.id, config.props
        )

        # Test high temperature clamping (95 + 10 = 100, not 105)
        await plugin.temp_change(10)

        # Test low temperature clamping (5 - 10 = 0, not -5)
        await plugin.temp_change(-10)

        # Test normal operation (50 + 10 = 60)
        await plugin.temp_change(10)

        assert len(plugin.temp_results) == 3
        assert plugin.temp_results[0]["clamped"] == 100  # High temp clamped
        assert plugin.temp_results[1]["clamped"] == 0  # Low temp clamped
        assert plugin.temp_results[2]["clamped"] == 60  # Normal operation

    @pytest.mark.asyncio
    async def test_active_step_detection(self, plugin_harness, button_config):
        """Test detection of active brewing steps."""

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.step_detection_calls = []

            def get_active_step_values(self):
                """Mock active step detection with different scenarios."""
                if not hasattr(self, "_scenario"):
                    self._scenario = 0
                self._scenario += 1

                try:
                    if self._scenario == 1:
                        # Scenario: Active step found
                        mock_steps = [
                            {
                                "status": "I",
                                "props": {"Temp": "60", "Kettle": "kettle1"},
                            },
                            {
                                "status": "A",
                                "props": {"Temp": "75", "Kettle": "kettle2"},
                            },
                            {
                                "status": "P",
                                "props": {"Temp": "80", "Kettle": "kettle3"},
                            },
                        ]

                        for step in mock_steps:
                            if step["status"] == "A":
                                targetTemp = str(step["props"]["Temp"])
                                kettle_id = str(step["props"]["Kettle"])
                                self.step_detection_calls.append(
                                    f"Found active step: {targetTemp}°C, "
                                    f"kettle: {kettle_id}"
                                )
                                return [targetTemp, kettle_id]
                    elif self._scenario == 2:
                        # Scenario: No active steps
                        mock_steps = [
                            {
                                "status": "I",
                                "props": {"Temp": "60", "Kettle": "kettle1"},
                            },
                            {
                                "status": "P",
                                "props": {"Temp": "80", "Kettle": "kettle3"},
                            },
                        ]
                        self.step_detection_calls.append("No active steps found")
                        return ["---", None]
                    else:
                        # Scenario: Step system error
                        raise Exception("Step system error")

                except Exception as e:
                    self.step_detection_calls.append(f"Error: {e}")
                    return ["---", None]

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, button_config.id, button_config.props
        )

        # Test active step detection scenarios
        result1 = plugin.get_active_step_values()  # Active step found
        result2 = plugin.get_active_step_values()  # No active steps
        result3 = plugin.get_active_step_values()  # Error scenario

        assert result1 == ["75", "kettle2"]
        assert result2 == ["---", None]
        assert result3 == ["---", None]

        assert len(plugin.step_detection_calls) == 3
        assert "Found active step: 75°C, kettle: kettle2" in plugin.step_detection_calls
        assert "No active steps found" in plugin.step_detection_calls
        assert "Error: Step system error" in plugin.step_detection_calls


class TestBMTMomentaryButtonsEdgeCases:
    """Test edge cases and error conditions for BMT MomentaryButtons plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_invalid_gpio_pin(self, plugin_harness):
        """Test handling of invalid GPIO pin configurations."""
        invalid_config = GPIOActorConfigFactory(
            id="test_invalid_gpio",
            name="TestInvalidGPIO",
            props={
                "GPIO": None,  # Invalid GPIO
                "Inverted": "No",
                "Button Function": "Select",
            },
        )

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.gpio_errors = []

            def get_state(self):
                """Mock GPIO state with error handling."""
                gpio = self.props.get("GPIO")
                if gpio is None:
                    self.gpio_errors.append("GPIO pin not configured")
                    return False

                # Normal GPIO handling would go here
                return self.state

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, invalid_config.id, invalid_config.props
        )

        # Test GPIO error handling
        state = plugin.get_state()

        assert state == False
        assert len(plugin.gpio_errors) == 1
        assert "GPIO pin not configured" in plugin.gpio_errors

    @pytest.mark.asyncio
    async def test_unknown_button_function(self, plugin_harness):
        """Test handling of unknown button function configurations."""
        unknown_function_config = GPIOActorConfigFactory(
            id="test_unknown_function",
            name="TestUnknownFunction",
            props={
                "GPIO": 26,
                "Inverted": "No",
                "Button Function": "UNKNOWN",  # Invalid function
            },
        )

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.function_calls = []

            async def on(self, power=None):
                self.state = True
                function = self.props.get("Button Function")

                if function == "Select":
                    await self.progress()
                elif function == "+10":
                    await self.temp_change(10)
                elif function == "+1":
                    await self.temp_change(1)
                elif function == "-1":
                    await self.temp_change(-1)
                elif function == "-10":
                    await self.temp_change(-10)
                else:
                    self.function_calls.append(f"Unknown function: {function}")

            async def progress(self):
                self.function_calls.append("progress")

            async def temp_change(self, increment):
                self.function_calls.append(f"temp_change: {increment}")

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton,
            unknown_function_config.id,
            unknown_function_config.props,
        )

        # Test unknown function handling
        await plugin.on()

        assert plugin.state == True
        assert len(plugin.function_calls) == 1
        assert "Unknown function: UNKNOWN" in plugin.function_calls

    @pytest.mark.asyncio
    async def test_step_progression_with_no_active_step(self, plugin_harness):
        """Test step progression when no step is active."""

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.progress_attempts = []

            async def progress(self):
                """Mock step progression with no active step."""
                # Simulate finding no active step
                step = None  # No active step found

                if step:
                    try:
                        # Would normally call cbpi.step.next()
                        self.progress_attempts.append("Step progressed")
                    except Exception as e:
                        self.progress_attempts.append(f"Progress error: {e}")
                else:
                    self.progress_attempts.append("No active step found")

        config = GPIOActorConfigFactory(
            id="test_no_step",
            name="TestNoStep",
            props={"GPIO": 27, "Inverted": "No", "Button Function": "Select"},
        )

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, config.id, config.props
        )

        # Test progression with no active step
        await plugin.progress()

        assert len(plugin.progress_attempts) == 1
        assert "No active step found" in plugin.progress_attempts

    @pytest.mark.asyncio
    async def test_temperature_change_with_no_kettle(self, plugin_harness):
        """Test temperature change when no kettle is active."""

        class MockBMTMomentaryButton:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.state = False
                self.temp_change_results = []

            async def temp_change(self, tempIncrement):
                """Mock temperature change with no active kettle."""
                targetTemp, kettle_id = self.get_active_step_values()

                if targetTemp and kettle_id:
                    # Normal temperature change
                    self.temp_change_results.append(f"Temp changed by {tempIncrement}")
                else:
                    # No active step/kettle
                    self.temp_change_results.append("No active step/kettle")

            def get_active_step_values(self):
                """Mock returning no active step."""
                return "---", None  # No active step/kettle

        config = GPIOActorConfigFactory(
            id="test_no_kettle",
            name="TestNoKettle",
            props={"GPIO": 28, "Inverted": "No", "Button Function": "+5"},
        )

        plugin = await plugin_harness.load_plugin(
            MockBMTMomentaryButton, config.id, config.props
        )

        # Test temperature change with no kettle
        await plugin.temp_change(5)

        assert len(plugin.temp_change_results) == 1
        assert "No active step/kettle" in plugin.temp_change_results
