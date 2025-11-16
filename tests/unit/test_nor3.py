"""
Unit tests for cbpi4-NOR3 plugin.

Tests the NOR3 logic gate actor functionality for 3-input NOR logic operations.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestNOR3:
    """Test suite for NOR3 (3-input NOR gate) plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness with GPIO mocking."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.fixture
    def mock_gpio(self):
        """Create a mocked RPi.GPIO interface."""
        return MockRPiGPIO()

    @pytest.fixture
    def nor3_config(self):
        """Create NOR3 plugin configuration."""
        return GPIOActorConfigFactory(
            id="test_nor3",
            name="TestNOR3",
            props={
                "GPIO": 18,
                "InputA": "actor_a",
                "InputB": "actor_b",
                "InputC": "actor_c",
                "Inverted": "No",
            },
        )

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_harness, nor3_config, mock_gpio):
        """Test plugin initialization with NOR3 logic configuration."""

        class MockNOR3:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio = int(props.get("GPIO", 18))
                self.input_a = props.get("InputA", "")
                self.input_b = props.get("InputB", "")
                self.input_c = props.get("InputC", "")
                self.inverted = props.get("Inverted", "No") == "Yes"
                self.state = False
                self.running = False
                self.task = None

            async def on_start(self):
                """Start the NOR3 logic processor."""
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                mock_gpio.output(self.gpio, mock_gpio.LOW)  # Initial state

                # Start logic evaluation task
                self.task = asyncio.create_task(self._logic_loop())

            async def on_stop(self):
                """Stop the NOR3 logic processor."""
                self.running = False
                if self.task:
                    self.task.cancel()
                mock_gpio.cleanup(self.gpio)

            async def _logic_loop(self):
                """Main logic evaluation loop."""
                while self.running:
                    # Get input states from other actors
                    state_a = await self._get_actor_state(self.input_a)
                    state_b = await self._get_actor_state(self.input_b)
                    state_c = await self._get_actor_state(self.input_c)

                    # Calculate NOR3 logic: NOT(A OR B OR C)
                    nor_result = not (state_a or state_b or state_c)

                    # Apply result to output
                    if nor_result != self.state:
                        self.state = nor_result
                        output_state = not nor_result if self.inverted else nor_result

                        if output_state:
                            mock_gpio.output(self.gpio, mock_gpio.HIGH)
                        else:
                            mock_gpio.output(self.gpio, mock_gpio.LOW)

                        await self.cbpi.actor.set_state(self.id, self.state)

                    await asyncio.sleep(0.1)  # Logic evaluation interval

            async def _get_actor_state(self, actor_id):
                """Get state of another actor."""
                if not actor_id:
                    return False
                try:
                    return await self.cbpi.actor.get_state(actor_id)
                except Exception:
                    return False

        plugin = await plugin_harness.load_plugin(MockNOR3, nor3_config.id, nor3_config.props)

        assert plugin.id == nor3_config.id
        assert plugin.gpio == 18
        assert plugin.input_a == "actor_a"
        assert plugin.input_b == "actor_b"
        assert plugin.input_c == "actor_c"
        assert plugin.inverted == False
        assert plugin.running == True

        # Initial state False (inputs False, NOR True, actor False)
        assert plugin.state == False

    @pytest.mark.asyncio
    async def test_nor3_logic_truth_table(self, plugin_harness, mock_gpio):
        """Test NOR3 logic truth table with all input combinations."""

        class MockNOR3:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.gpio = int(props.get("GPIO", 18))
                self.inverted = props.get("Inverted", "No") == "Yes"
                self.state = False
                self.running = False

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)

            async def on_stop(self):
                self.running = False
                mock_gpio.cleanup(self.gpio)

            def calculate_nor3(self, a, b, c):
                """Calculate NOR3 logic result."""
                nor_result = not (a or b or c)
                self.state = nor_result

                output_state = not nor_result if self.inverted else nor_result
                if output_state:
                    mock_gpio.output(self.gpio, mock_gpio.HIGH)
                else:
                    mock_gpio.output(self.gpio, mock_gpio.LOW)

                return nor_result

        plugin = await plugin_harness.load_plugin(MockNOR3, "test_nor3_logic", {"GPIO": 18, "Inverted": "No"})

        # Test all 8 combinations of 3 inputs
        truth_table = [
            # A, B, C -> NOR3 result
            (False, False, False, True),  # 0,0,0 -> 1
            (False, False, True, False),  # 0,0,1 -> 0
            (False, True, False, False),  # 0,1,0 -> 0
            (False, True, True, False),  # 0,1,1 -> 0
            (True, False, False, False),  # 1,0,0 -> 0
            (True, False, True, False),  # 1,0,1 -> 0
            (True, True, False, False),  # 1,1,0 -> 0
            (True, True, True, False),  # 1,1,1 -> 0
        ]

        for a, b, c, expected in truth_table:
            result = plugin.calculate_nor3(a, b, c)
            assert result == expected, f"NOR3({a},{b},{c}) should be {expected}, got {result}"

            # Verify GPIO output matches logic result (for non-inverted)
            expected_gpio = mock_gpio.HIGH if expected else mock_gpio.LOW
            assert mock_gpio.input(plugin.gpio) == expected_gpio

    @pytest.mark.asyncio
    async def test_inverted_nor3_logic(self, plugin_harness, mock_gpio):
        """Test inverted NOR3 logic output."""

        class MockNOR3:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.gpio = int(props.get("GPIO", 18))
                self.inverted = props.get("Inverted", "No") == "Yes"
                self.state = False
                self.running = False

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)

            async def on_stop(self):
                self.running = False
                mock_gpio.cleanup(self.gpio)

            def calculate_nor3_inverted(self, a, b, c):
                """Calculate inverted NOR3 logic result."""
                nor_result = not (a or b or c)
                self.state = nor_result

                # Invert the output
                output_state = not nor_result
                if output_state:
                    mock_gpio.output(self.gpio, mock_gpio.HIGH)
                else:
                    mock_gpio.output(self.gpio, mock_gpio.LOW)

                return output_state  # Return inverted result for testing

        plugin = await plugin_harness.load_plugin(MockNOR3, "test_inverted_nor3", {"GPIO": 18, "Inverted": "Yes"})

        assert plugin.inverted == True

        # Test key cases for inverted logic
        test_cases = [
            (False, False, False, False),  # NOR3=True, Inverted=False -> GPIO LOW
            (False, False, True, True),  # NOR3=False, Inverted=True -> GPIO HIGH
            (True, True, True, True),  # NOR3=False, Inverted=True -> GPIO HIGH
        ]

        for a, b, c, expected_gpio_high in test_cases:
            gpio_result = plugin.calculate_nor3_inverted(a, b, c)
            expected_gpio = mock_gpio.HIGH if expected_gpio_high else mock_gpio.LOW
            assert mock_gpio.input(plugin.gpio) == expected_gpio

    @pytest.mark.asyncio
    async def test_dynamic_input_monitoring(self, plugin_harness, mock_gpio):
        """Test dynamic monitoring of input actor states."""

        class MockNOR3:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.gpio = int(props.get("GPIO", 18))
                self.input_a = props.get("InputA", "")
                self.input_b = props.get("InputB", "")
                self.input_c = props.get("InputC", "")
                self.state = False
                self.running = False
                self.task = None
                self.evaluation_count = 0

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                mock_gpio.output(self.gpio, mock_gpio.LOW)
                self.task = asyncio.create_task(self._logic_loop())

            async def on_stop(self):
                self.running = False
                if self.task:
                    self.task.cancel()
                mock_gpio.cleanup(self.gpio)

            async def _logic_loop(self):
                """Logic evaluation loop with counting."""
                while self.running:
                    self.evaluation_count += 1

                    # Get input states (simulated)
                    state_a = await self.cbpi.actor.get_state(self.input_a) if self.input_a else False
                    state_b = await self.cbpi.actor.get_state(self.input_b) if self.input_b else False
                    state_c = await self.cbpi.actor.get_state(self.input_c) if self.input_c else False

                    # Calculate NOR3
                    nor_result = not (state_a or state_b or state_c)

                    if nor_result != self.state:
                        self.state = nor_result
                        output_level = mock_gpio.HIGH if nor_result else mock_gpio.LOW
                        mock_gpio.output(self.gpio, output_level)
                        await self.cbpi.actor.set_state(self.id, self.state)

                    await asyncio.sleep(0.05)  # Fast evaluation for testing

        # Set up some mock actor states
        plugin_harness.cbpi.actor._actor_states["input_a"] = False
        plugin_harness.cbpi.actor._actor_states["input_b"] = False
        plugin_harness.cbpi.actor._actor_states["input_c"] = False

        plugin = await plugin_harness.load_plugin(
            MockNOR3,
            "test_dynamic",
            {"GPIO": 18, "InputA": "input_a", "InputB": "input_b", "InputC": "input_c"},
        )

        # Wait for initial evaluation
        await asyncio.sleep(0.2)

        # Should have evaluated multiple times
        assert plugin.evaluation_count > 0

        # Initial state: all inputs False -> NOR3 True
        assert plugin.state == True
        assert mock_gpio.input(plugin.gpio) == mock_gpio.HIGH

        # Change an input state
        plugin_harness.cbpi.actor._actor_states["input_a"] = True

        # Wait for re-evaluation
        await asyncio.sleep(0.2)

        # Should now be False (one input is True)
        assert plugin.state == False
        assert mock_gpio.input(plugin.gpio) == mock_gpio.LOW

    def test_plugin_configuration_validation(self, nor3_config):
        """Test plugin configuration validation."""
        from tests.fixtures.test_data import validate_plugin_config

        # Valid configuration should pass
        errors = validate_plugin_config(nor3_config)
        assert len(errors) == 0

        # Missing inputs should still be valid (will default to False)
        minimal_config = GPIOActorConfigFactory(id="test_minimal_nor3", props={"GPIO": 18})
        errors = validate_plugin_config(minimal_config)
        assert len(errors) == 0


class TestNOR3EdgeCases:
    """Test edge cases and error conditions for NOR3 plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_missing_input_actors(self, plugin_harness, mock_gpio):
        """Test behavior when input actors don't exist."""

        class MockNOR3:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.gpio = int(props.get("GPIO", 18))
                self.input_a = props.get("InputA", "")
                self.missing_actor_errors = 0
                self.running = False

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)

            async def on_stop(self):
                self.running = False
                mock_gpio.cleanup(self.gpio)

            async def get_input_state_safe(self, actor_id):
                """Safely get actor state with error handling."""
                if not actor_id:
                    return False

                try:
                    return await self.cbpi.actor.get_state(actor_id)
                except Exception:
                    self.missing_actor_errors += 1
                    return False  # Default to False for missing actors

        plugin = await plugin_harness.load_plugin(
            MockNOR3,
            "test_missing_inputs",
            {
                "GPIO": 18,
                "InputA": "nonexistent_actor",
                "InputB": "",  # Empty input
                "InputC": "another_missing_actor",
            },
        )

        # Test safe input retrieval
        state_a = await plugin.get_input_state_safe("nonexistent_actor")
        state_b = await plugin.get_input_state_safe("")
        state_c = await plugin.get_input_state_safe("another_missing_actor")

        # Should default to False for missing actors
        assert state_a == False
        assert state_b == False
        assert state_c == False

        # Should have detected missing actor errors
        assert plugin.missing_actor_errors >= 2

    @pytest.mark.asyncio
    async def test_empty_input_configuration(self, plugin_harness, mock_gpio):
        """Test NOR3 with no input actors configured."""

        class MockNOR3:
            _plugin_type = "Actor"

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.gpio = int(props.get("GPIO", 18))
                self.input_a = props.get("InputA", "").strip()
                self.input_b = props.get("InputB", "").strip()
                self.input_c = props.get("InputC", "").strip()
                self.state = False
                self.running = False

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                # NOR3 result True with all inputs False
                self.state = True
                mock_gpio.output(self.gpio, mock_gpio.HIGH)

            async def on_stop(self):
                self.running = False
                mock_gpio.cleanup(self.gpio)

        plugin = await plugin_harness.load_plugin(MockNOR3, "test_no_inputs", {"GPIO": 18})  # No input actors specified

        # Should handle empty configuration gracefully
        assert plugin.input_a == ""
        assert plugin.input_b == ""
        assert plugin.input_c == ""

        # With no inputs (all False), NOR3 should be True
        assert plugin.state == True
        assert mock_gpio.input(plugin.gpio) == mock_gpio.HIGH
