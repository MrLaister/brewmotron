"""
Unit tests for cbpi4-OneAtATime plugin.

Tests the One-at-a-Time actor coordination functionality to prevent 
simultaneous operation of multiple actors.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import MockRPiGPIO, HardwareTestHarness
from tests.fixtures.test_data import PluginConfigFactory, GPIOActorConfigFactory

# Mark all tests in this module as hardware tests
pytestmark = pytest.mark.hardware


class TestOneAtATime:
    """Test suite for OneAtATime plugin."""

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
    def coordination_config(self):
        """Create OneAtATime plugin configuration."""
        return GPIOActorConfigFactory(
            id="test_one_at_a_time",
            name="TestOneAtATime",
            props={"GPIO": 18, "Inverted": "No", "CoordinationGroup": "heaters"},
        )

    @pytest.mark.asyncio
    async def test_plugin_initialization(
        self, plugin_harness, coordination_config, mock_gpio
    ):
        """Test plugin initialization with coordination parameters."""

        class MockOneAtATime:
            _plugin_type = "Actor"
            coordination_groups = {}  # Class-level coordination state

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio = int(props.get("GPIO", 18))
                self.inverted = props.get("Inverted", "No") == "Yes"
                self.group = props.get("CoordinationGroup", "default")
                self.state = False
                self.running = False

                # Initialize coordination group
                if self.group not in MockOneAtATime.coordination_groups:
                    MockOneAtATime.coordination_groups[self.group] = {
                        "active_actor": None,
                        "waiting_actors": [],
                    }

            async def on_start(self):
                """Start the actor with coordination."""
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                if self.inverted:
                    mock_gpio.output(
                        self.gpio, mock_gpio.HIGH
                    )  # OFF state for inverted
                else:
                    mock_gpio.output(self.gpio, mock_gpio.LOW)  # OFF state for normal

            async def on_stop(self):
                """Stop the actor and release coordination."""
                self.running = False
                await self.off()
                mock_gpio.cleanup(self.gpio)

                # Remove from coordination group
                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] == self.id:
                    group_state["active_actor"] = None
                    # Activate next waiting actor
                    if group_state["waiting_actors"]:
                        next_actor = group_state["waiting_actors"].pop(0)
                        # In real implementation, would signal next actor

            async def on(self, power=100):
                """Turn on with coordination check."""
                group_state = MockOneAtATime.coordination_groups[self.group]

                # Check if another actor in group is already active
                if (
                    group_state["active_actor"] is not None
                    and group_state["active_actor"] != self.id
                ):
                    # Add to waiting list
                    if self.id not in group_state["waiting_actors"]:
                        group_state["waiting_actors"].append(self.id)
                    return False  # Cannot turn on yet

                # Activate this actor
                group_state["active_actor"] = self.id
                self.state = True

                if self.inverted:
                    mock_gpio.output(self.gpio, mock_gpio.LOW)
                else:
                    mock_gpio.output(self.gpio, mock_gpio.HIGH)

                await self.cbpi.actor.set_state(self.id, True)
                return True

            async def off(self):
                """Turn off and allow next actor."""
                self.state = False

                if self.inverted:
                    mock_gpio.output(self.gpio, mock_gpio.HIGH)
                else:
                    mock_gpio.output(self.gpio, mock_gpio.LOW)

                await self.cbpi.actor.set_state(self.id, False)

                # Release coordination
                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] == self.id:
                    group_state["active_actor"] = None

                    # Activate next waiting actor
                    if group_state["waiting_actors"]:
                        next_actor_id = group_state["waiting_actors"].pop(0)
                        # In real implementation, would signal the next actor to turn on

        plugin = await plugin_harness.load_plugin(
            MockOneAtATime, coordination_config.id, coordination_config.props
        )

        assert plugin.id == coordination_config.id
        assert plugin.gpio == 18
        assert plugin.inverted == False
        assert plugin.group == "heaters"
        assert plugin.running == True
        assert plugin.state == False

        # Verify coordination group was created
        assert "heaters" in MockOneAtATime.coordination_groups
        assert MockOneAtATime.coordination_groups["heaters"]["active_actor"] is None

    @pytest.mark.asyncio
    async def test_coordination_prevents_simultaneous_operation(
        self, plugin_harness, mock_gpio
    ):
        """Test that only one actor in a group can be active at a time."""
        # Create multiple actors in the same coordination group
        actor_configs = [
            GPIOActorConfigFactory(
                id="heater1", props={"GPIO": 18, "CoordinationGroup": "heaters"}
            ),
            GPIOActorConfigFactory(
                id="heater2", props={"GPIO": 19, "CoordinationGroup": "heaters"}
            ),
            GPIOActorConfigFactory(
                id="heater3", props={"GPIO": 20, "CoordinationGroup": "heaters"}
            ),
        ]

        class MockOneAtATime:
            _plugin_type = "Actor"
            coordination_groups = {}

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio = int(props.get("GPIO", 18))
                self.group = props.get("CoordinationGroup", "default")
                self.state = False
                self.running = False

                if self.group not in MockOneAtATime.coordination_groups:
                    MockOneAtATime.coordination_groups[self.group] = {
                        "active_actor": None,
                        "waiting_actors": [],
                    }

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                mock_gpio.output(self.gpio, mock_gpio.LOW)

            async def on_stop(self):
                self.running = False
                await self.off()
                mock_gpio.cleanup(self.gpio)

            async def on(self, power=100):
                group_state = MockOneAtATime.coordination_groups[self.group]

                if (
                    group_state["active_actor"] is not None
                    and group_state["active_actor"] != self.id
                ):
                    if self.id not in group_state["waiting_actors"]:
                        group_state["waiting_actors"].append(self.id)
                    return False

                group_state["active_actor"] = self.id
                self.state = True
                mock_gpio.output(self.gpio, mock_gpio.HIGH)
                await self.cbpi.actor.set_state(self.id, True)
                return True

            async def off(self):
                self.state = False
                mock_gpio.output(self.gpio, mock_gpio.LOW)
                await self.cbpi.actor.set_state(self.id, False)

                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] == self.id:
                    group_state["active_actor"] = None

        # Load all actors
        actors = []
        for config in actor_configs:
            actor = await plugin_harness.load_plugin(
                MockOneAtATime, config.id, config.props
            )
            actors.append(actor)

        # Try to turn on first actor - should succeed
        result1 = await actors[0].on()
        assert result1 == True
        assert actors[0].state == True
        assert mock_gpio.input(actors[0].gpio) == mock_gpio.HIGH

        # Try to turn on second actor - should be blocked
        result2 = await actors[1].on()
        assert result2 == False
        assert actors[1].state == False
        assert mock_gpio.input(actors[1].gpio) == mock_gpio.LOW

        # Try to turn on third actor - should also be blocked
        result3 = await actors[2].on()
        assert result3 == False
        assert actors[2].state == False
        assert mock_gpio.input(actors[2].gpio) == mock_gpio.LOW

        # Verify coordination state
        group_state = MockOneAtATime.coordination_groups["heaters"]
        assert group_state["active_actor"] == "heater1"
        assert "heater2" in group_state["waiting_actors"]
        assert "heater3" in group_state["waiting_actors"]

    @pytest.mark.asyncio
    async def test_actor_queue_management(self, plugin_harness, mock_gpio):
        """Test actor queue management when one turns off."""

        class MockOneAtATime:
            _plugin_type = "Actor"
            coordination_groups = {}

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio = int(props.get("GPIO", 18))
                self.group = props.get("CoordinationGroup", "default")
                self.state = False
                self.running = False

                if self.group not in MockOneAtATime.coordination_groups:
                    MockOneAtATime.coordination_groups[self.group] = {
                        "active_actor": None,
                        "waiting_actors": [],
                    }

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                mock_gpio.output(self.gpio, mock_gpio.LOW)

            async def on_stop(self):
                self.running = False
                await self.off()
                mock_gpio.cleanup(self.gpio)

            async def on(self, power=100):
                group_state = MockOneAtATime.coordination_groups[self.group]

                if (
                    group_state["active_actor"] is not None
                    and group_state["active_actor"] != self.id
                ):
                    if self.id not in group_state["waiting_actors"]:
                        group_state["waiting_actors"].append(self.id)
                    return False

                group_state["active_actor"] = self.id
                self.state = True
                mock_gpio.output(self.gpio, mock_gpio.HIGH)
                await self.cbpi.actor.set_state(self.id, True)
                return True

            async def off(self):
                self.state = False
                mock_gpio.output(self.gpio, mock_gpio.LOW)
                await self.cbpi.actor.set_state(self.id, False)

                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] == self.id:
                    group_state["active_actor"] = None

            def get_queue_position(self):
                """Get position in waiting queue."""
                group_state = MockOneAtATime.coordination_groups[self.group]
                if self.id in group_state["waiting_actors"]:
                    return group_state["waiting_actors"].index(self.id) + 1
                return 0

        # Create actors
        actor1 = await plugin_harness.load_plugin(
            MockOneAtATime, "actor1", {"GPIO": 18, "CoordinationGroup": "test_group"}
        )

        actor2 = await plugin_harness.load_plugin(
            MockOneAtATime, "actor2", {"GPIO": 19, "CoordinationGroup": "test_group"}
        )

        actor3 = await plugin_harness.load_plugin(
            MockOneAtATime, "actor3", {"GPIO": 20, "CoordinationGroup": "test_group"}
        )

        # Turn on first actor
        await actor1.on()
        assert actor1.state == True

        # Queue up other actors
        await actor2.on()
        await actor3.on()

        # Check queue positions
        assert actor2.get_queue_position() == 1  # First in queue
        assert actor3.get_queue_position() == 2  # Second in queue

        # Turn off first actor
        await actor1.off()
        assert actor1.state == False

        # Verify queue management
        group_state = MockOneAtATime.coordination_groups["test_group"]
        assert group_state["active_actor"] is None
        assert len(group_state["waiting_actors"]) == 2

    @pytest.mark.asyncio
    async def test_different_coordination_groups(self, plugin_harness, mock_gpio):
        """Test that different coordination groups don't interfere."""

        class MockOneAtATime:
            _plugin_type = "Actor"
            coordination_groups = {}

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.props = props
                self.gpio = int(props.get("GPIO", 18))
                self.group = props.get("CoordinationGroup", "default")
                self.state = False
                self.running = False

                if self.group not in MockOneAtATime.coordination_groups:
                    MockOneAtATime.coordination_groups[self.group] = {
                        "active_actor": None,
                        "waiting_actors": [],
                    }

            async def on_start(self):
                self.running = True
                mock_gpio.setup(self.gpio, mock_gpio.OUT)
                mock_gpio.output(self.gpio, mock_gpio.LOW)

            async def on_stop(self):
                self.running = False
                await self.off()
                mock_gpio.cleanup(self.gpio)

            async def on(self, power=100):
                group_state = MockOneAtATime.coordination_groups[self.group]

                if (
                    group_state["active_actor"] is not None
                    and group_state["active_actor"] != self.id
                ):
                    return False

                group_state["active_actor"] = self.id
                self.state = True
                mock_gpio.output(self.gpio, mock_gpio.HIGH)
                await self.cbpi.actor.set_state(self.id, True)
                return True

            async def off(self):
                self.state = False
                mock_gpio.output(self.gpio, mock_gpio.LOW)
                await self.cbpi.actor.set_state(self.id, False)

                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] == self.id:
                    group_state["active_actor"] = None

        # Create actors in different groups
        heater1 = await plugin_harness.load_plugin(
            MockOneAtATime, "heater1", {"GPIO": 18, "CoordinationGroup": "heaters"}
        )

        pump1 = await plugin_harness.load_plugin(
            MockOneAtATime, "pump1", {"GPIO": 19, "CoordinationGroup": "pumps"}
        )

        # Both should be able to turn on simultaneously (different groups)
        result1 = await heater1.on()
        assert result1 == True
        assert heater1.state == True

        result2 = await pump1.on()
        assert result2 == True
        assert pump1.state == True

        # Both should be active in their respective groups
        assert (
            MockOneAtATime.coordination_groups["heaters"]["active_actor"] == "heater1"
        )
        assert MockOneAtATime.coordination_groups["pumps"]["active_actor"] == "pump1"

    def test_plugin_configuration_validation(self, coordination_config):
        """Test plugin configuration validation."""
        from tests.fixtures.test_data import validate_plugin_config

        # Valid configuration should pass
        errors = validate_plugin_config(coordination_config)
        assert len(errors) == 0

        # Missing coordination group should use default
        config_no_group = coordination_config
        del config_no_group.props["CoordinationGroup"]

        # Should still be valid (will use default group)
        errors = validate_plugin_config(config_no_group)
        assert len(errors) == 0


class TestOneAtATimeEdgeCases:
    """Test edge cases and error conditions for OneAtATime plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_empty_coordination_group(self, plugin_harness, mock_gpio):
        """Test behavior with empty coordination group name."""
        config = GPIOActorConfigFactory(
            id="test_empty_group", props={"GPIO": 18, "CoordinationGroup": ""}
        )

        class MockOneAtATime:
            _plugin_type = "Actor"
            coordination_groups = {}

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.group = props.get("CoordinationGroup", "default").strip()
                if not self.group:
                    self.group = "default"  # Fallback to default

                if self.group not in MockOneAtATime.coordination_groups:
                    MockOneAtATime.coordination_groups[self.group] = {
                        "active_actor": None,
                        "waiting_actors": [],
                    }
                self.running = False

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False

        plugin = await plugin_harness.load_plugin(
            MockOneAtATime, config.id, config.props
        )

        # Should use default group
        assert plugin.group == "default"
        assert "default" in MockOneAtATime.coordination_groups

    @pytest.mark.asyncio
    async def test_coordination_group_cleanup_on_stop(self, plugin_harness, mock_gpio):
        """Test coordination group cleanup when actors stop."""

        class MockOneAtATime:
            _plugin_type = "Actor"
            coordination_groups = {}

            def __init__(self, cbpi, id, props):
                self.cbpi = cbpi
                self.id = id
                self.group = props.get("CoordinationGroup", "default")
                self.state = False
                self.running = False

                if self.group not in MockOneAtATime.coordination_groups:
                    MockOneAtATime.coordination_groups[self.group] = {
                        "active_actor": None,
                        "waiting_actors": [],
                    }

            async def on_start(self):
                self.running = True

            async def on_stop(self):
                self.running = False
                # Clean up coordination state
                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] == self.id:
                    group_state["active_actor"] = None
                if self.id in group_state["waiting_actors"]:
                    group_state["waiting_actors"].remove(self.id)

            async def on(self, power=100):
                group_state = MockOneAtATime.coordination_groups[self.group]
                if group_state["active_actor"] is None:
                    group_state["active_actor"] = self.id
                    self.state = True
                    return True
                return False

        plugin = await plugin_harness.load_plugin(
            MockOneAtATime,
            "test_cleanup",
            {"GPIO": 18, "CoordinationGroup": "cleanup_test"},
        )

        # Turn on actor
        await plugin.on()
        assert plugin.state == True

        group_state = MockOneAtATime.coordination_groups["cleanup_test"]
        assert group_state["active_actor"] == "test_cleanup"

        # Stop plugin
        await plugin_harness.unload_plugin("test_cleanup")

        # Should have cleaned up coordination state
        assert group_state["active_actor"] is None
