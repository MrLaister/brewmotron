"""
Integration tests for OneAtATime actor coordination.

Tests the complex coordination logic that prevents multiple high-power 
actors from operating simultaneously, ensuring safe brewing operations
and preventing electrical overload conditions.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import async_timeout
import pytest
import pytest_asyncio

logger = logging.getLogger(__name__)

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, MockCBPiActorBase, PluginTestHarness
from tests.fixtures.hardware_mocks import HardwareTestHarness, MockRPiGPIO
from tests.fixtures.test_data import GPIOActorConfigFactory, PluginConfigFactory

# Cache handler utilities
from brewmotron_cache_handler import reset_cache_handler

# Mark all tests in this module as integration tests
# Phase 8: Re-enabled after Phase 7 plugin migration to cache handler
pytestmark = [
    pytest.mark.integration,
]


class MockOneAtATimeActor(MockCBPiActorBase):
    """Mock implementation of OneAtATime actor for integration testing."""

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.coordination_group = props.get("OneAtATime group", 1)
        self.controlled_actor = props.get("actor")
        self.coordinator = None

    async def on_start(self):
        """Initialize actor and register with coordination system."""
        # Get or create coordinator for this group
        if not hasattr(self.cbpi, "_coordinators"):
            self.cbpi._coordinators = {}

        if self.coordination_group not in self.cbpi._coordinators:
            self.cbpi._coordinators[self.coordination_group] = ActorCoordinator(self.coordination_group)

        self.coordinator = self.cbpi._coordinators[self.coordination_group]
        await self.coordinator.register_actor(self)

    async def on(self, power=None):
        """Turn actor on through coordination system."""
        if self.coordinator:
            return await self.coordinator.turn_on_actor(self.id, power)
        else:
            await super().on(power)

    async def off(self):
        """Turn actor off."""
        if self.coordinator:
            await self.coordinator.turn_off_actor(self.id)
        else:
            await super().off()

    async def on_stop(self):
        """Cleanup coordination registration."""
        if self.coordinator:
            await self.coordinator.unregister_actor(self.id)


class MockGPIOActor(MockCBPiActorBase):
    """Mock GPIO actor for coordination testing."""

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.gpio_pin = int(props.get("GPIO", 18))
        self.inverted = props.get("Inverted", "No") == "Yes"
        self.gpio = MockRPiGPIO()

    async def on_start(self):
        """Setup GPIO pin."""
        self.gpio.setup(self.gpio_pin, self.gpio.OUT)

    async def on(self, power=None):
        """Turn GPIO actor on."""
        await super().on(power)
        output_value = self.gpio.LOW if self.inverted else self.gpio.HIGH
        self.gpio.output(self.gpio_pin, output_value)

    async def off(self):
        """Turn GPIO actor off."""
        await super().off()
        output_value = self.gpio.HIGH if self.inverted else self.gpio.LOW
        self.gpio.output(self.gpio_pin, output_value)


class ActorCoordinator:
    """Coordination system for OneAtATime actors."""

    @pytest_asyncio.fixture(autouse=True)
    async def reset_cache_between_tests(self):
        """Reset cache handler singleton between tests for isolation."""
        await reset_cache_handler()
        yield
        await reset_cache_handler()

    def __init__(self, group_id):
        self.group_id = group_id
        self.actors = {}
        self.active_actor = None
        self.coordination_lock = asyncio.Lock()
        self._cleanup_tasks = set()

    async def register_actor(self, actor):
        """Register an actor for coordination."""
        self.actors[actor.id] = actor

    async def unregister_actor(self, actor_id):
        """Remove actor from coordination."""
        if actor_id in self.actors:
            del self.actors[actor_id]
        if self.active_actor == actor_id:
            self.active_actor = None

    async def turn_on_actor(self, actor_id, power=None):
        """Turn on actor with coordination logic."""
        try:
            # Use timeout to prevent deadlocks
            async with async_timeout.timeout(5.0):
                async with self.coordination_lock:
                    # Turn off currently active actor if different
                    if self.active_actor and self.active_actor != actor_id:
                        if self.active_actor in self.actors:
                            active_actor = self.actors[self.active_actor]
                            # Call parent off() method directly to
                            # avoid re-acquiring lock
                            await MockCBPiActorBase.off(active_actor)
                            self.active_actor = None

                    # Turn on requested actor
                    if actor_id in self.actors:
                        actor = self.actors[actor_id]
                        await MockCBPiActorBase.on(actor, power)  # Call parent on() method
                        self.active_actor = actor_id
                        return True

                    return False
        except asyncio.TimeoutError:
            logger.warning(f"Timeout turning on actor {actor_id}")
            return False

    async def turn_off_actor(self, actor_id):
        """Turn off specific actor."""
        try:
            # Use timeout to prevent deadlocks
            async with async_timeout.timeout(5.0):
                async with self.coordination_lock:
                    if actor_id in self.actors:
                        actor = self.actors[actor_id]
                        await MockCBPiActorBase.off(actor)  # Call parent off() method

                        if self.active_actor == actor_id:
                            self.active_actor = None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout turning off actor {actor_id}")
        except Exception as e:
            logger.warning(f"Error turning off actor {actor_id}: {e}")

    def get_active_actor(self):
        """Get currently active actor ID."""
        return self.active_actor

    def get_actor_count(self):
        """Get number of registered actors."""
        return len(self.actors)

    async def cleanup(self):
        """Clean up coordinator resources."""
        # Cancel any pending tasks
        for task in list(self._cleanup_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._cleanup_tasks.clear()

        # Clear actors
        self.actors.clear()
        self.active_actor = None


class TestActorCoordination:
    """Integration test suite for OneAtATime actor coordination."""

    @pytest_asyncio.fixture
    async def coordination_harness(self):
        """Create a test harness with multiple coordinated actors."""
        harness = PluginTestHarness()

        # Create three actors in same coordination group
        mash_heater = await harness.load_plugin(
            MockOneAtATimeActor,
            "mash_heater",
            {"actor": "mash_heater_gpio", "OneAtATime group": 1},
        )

        boil_heater = await harness.load_plugin(
            MockOneAtATimeActor,
            "boil_heater",
            {"actor": "boil_heater_gpio", "OneAtATime group": 1},
        )

        pump = await harness.load_plugin(
            MockOneAtATimeActor,
            "circulation_pump",
            {"actor": "pump_gpio", "OneAtATime group": 1},
        )

        # Create one actor in different group (should not interfere)
        separate_pump = await harness.load_plugin(
            MockOneAtATimeActor,
            "separate_pump",
            {"actor": "separate_pump_gpio", "OneAtATime group": 2},
        )

        yield {
            "harness": harness,
            "mash_heater": mash_heater,
            "boil_heater": boil_heater,
            "pump": pump,
            "separate_pump": separate_pump,
        }

        # Clean up coordinators first
        if hasattr(harness.cbpi, "_coordinators"):
            for coordinator in harness.cbpi._coordinators.values():
                await coordinator.cleanup()
            harness.cbpi._coordinators.clear()

        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_basic_actor_coordination(self, coordination_harness):
        """Test that only one actor in a group can be active at a time."""
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]
        pump = coordination_harness["pump"]

        # Turn on mash heater
        await mash_heater.on(100)
        assert mash_heater.state == True, "Mash heater should be on"
        assert mash_heater.power == 100, "Mash heater should have full power"

        # Turn on boil heater - should turn off mash heater
        await boil_heater.on(80)
        assert boil_heater.state == True, "Boil heater should be on"
        assert boil_heater.power == 80, "Boil heater should have 80% power"
        assert mash_heater.state == False, "Mash heater should be turned off"

        # Turn on pump - should turn off boil heater
        await pump.on(50)
        assert pump.state == True, "Pump should be on"
        assert pump.power == 50, "Pump should have 50% power"
        assert boil_heater.state == False, "Boil heater should be turned off"
        assert mash_heater.state == False, "Mash heater should remain off"

    @pytest.mark.asyncio
    async def test_coordination_groups_isolation(self, coordination_harness):
        """Test that actors in different groups don't interfere with each other."""
        mash_heater = coordination_harness["mash_heater"]  # group 1
        separate_pump = coordination_harness["separate_pump"]  # group 2

        # Turn on both actors (in different groups)
        await mash_heater.on(100)
        await separate_pump.on(75)

        # Both should remain active since they're in different coordination groups
        assert mash_heater.state == True, "Mash heater should remain on"
        assert separate_pump.state == True, "Separate pump should remain on"
        assert mash_heater.power == 100, "Mash heater power should be preserved"
        assert separate_pump.power == 75, "Separate pump power should be preserved"

    @pytest.mark.asyncio
    async def test_explicit_actor_off(self, coordination_harness):
        """Test explicitly turning off actors."""
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]

        # Turn on mash heater
        await mash_heater.on(100)
        assert mash_heater.state == True, "Mash heater should be on"

        # Explicitly turn off mash heater
        await mash_heater.off()
        assert mash_heater.state == False, "Mash heater should be off"

        # Turn on boil heater (no other actors should be affected)
        await boil_heater.on(90)
        assert boil_heater.state == True, "Boil heater should be on"
        assert mash_heater.state == False, "Mash heater should remain off"

    @pytest.mark.asyncio
    async def test_coordinator_state_tracking(self, coordination_harness):
        """Test that coordinator correctly tracks active actor state."""
        harness = coordination_harness["harness"]
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]
        pump = coordination_harness["pump"]

        # Get coordinator for group 1
        coordinator = harness.cbpi._coordinators[1]

        # Initially no active actor
        assert coordinator.get_active_actor() is None, "No actor should be active initially"
        assert coordinator.get_actor_count() == 3, "Should have 3 registered actors"

        # Turn on mash heater
        await mash_heater.on()
        assert coordinator.get_active_actor() == "mash_heater", "Mash heater should be active"

        # Switch to boil heater
        await boil_heater.on()
        assert coordinator.get_active_actor() == "boil_heater", "Boil heater should be active"

        # Turn off boil heater
        await boil_heater.off()
        assert coordinator.get_active_actor() is None, "No actor should be active after turning off"

    @pytest.mark.asyncio
    async def test_concurrent_actor_requests(self, coordination_harness):
        """Test coordination under concurrent actor activation requests."""
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]
        pump = coordination_harness["pump"]

        # Create concurrent tasks to turn on different actors
        tasks = [
            asyncio.create_task(mash_heater.on(100)),
            asyncio.create_task(boil_heater.on(80)),
            asyncio.create_task(pump.on(60)),
        ]

        try:
            # Wait for all tasks to complete with timeout
            async with async_timeout.timeout(5.0):
                results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Task {i} failed: {result}")

        except asyncio.TimeoutError:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise AssertionError("Concurrent actor test timed out")

        # Only one actor should be active
        active_count = sum([mash_heater.state, boil_heater.state, pump.state])

        assert active_count == 1, f"Only one actor should be active, got {active_count}"

        # One of the actors should have succeeded
        assert any([mash_heater.state, boil_heater.state, pump.state]), "At least one actor should be active"

    @pytest.mark.asyncio
    async def test_actor_power_level_preservation(self, coordination_harness):
        """Test that power levels are preserved during coordination switches."""
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]

        # Turn on mash heater with specific power
        await mash_heater.on(75)
        assert mash_heater.power == 75, "Mash heater power should be 75%"

        # Turn on boil heater with different power
        await boil_heater.on(90)
        assert boil_heater.power == 90, "Boil heater power should be 90%"
        assert mash_heater.power == 0, "Mash heater power should be reset when turned off"

        # Turn mash heater back on with new power level
        await mash_heater.on(60)
        assert mash_heater.power == 60, "Mash heater power should be 60%"
        assert boil_heater.power == 0, "Boil heater power should be reset when turned off"

    @pytest.mark.asyncio
    async def test_coordination_timing_and_race_conditions(self, coordination_harness):
        """Test coordination system under timing stress and race conditions."""
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]
        pump = coordination_harness["pump"]

        # Rapid switching between actors with timeout protection
        try:
            async with async_timeout.timeout(10.0):  # Overall test timeout
                for i in range(10):
                    actors = [mash_heater, boil_heater, pump]
                    selected_actor = actors[i % 3]

                    await selected_actor.on(50 + i * 5)  # Varying power levels

                    # Short delay to simulate real-world timing
                    await asyncio.sleep(0.01)  # Reduced delay to speed up test

                    # Verify only one actor is active
                    active_actors = [a for a in actors if a.state]
                    assert len(active_actors) == 1, f"Only one actor should be active, iteration {i}"
                    assert active_actors[0] == selected_actor, f"Wrong actor active at iteration {i}"
        except asyncio.TimeoutError:
            raise AssertionError("Timing stress test timed out")

    @pytest.mark.asyncio
    async def test_coordination_error_recovery(self, coordination_harness):
        """Test coordination system recovery from error conditions."""
        harness = coordination_harness["harness"]
        mash_heater = coordination_harness["mash_heater"]
        boil_heater = coordination_harness["boil_heater"]

        # Get coordinator
        coordinator = harness.cbpi._coordinators[1]

        # Turn on mash heater
        await mash_heater.on(100)
        assert coordinator.get_active_actor() == "mash_heater"

        # Simulate error by manually corrupting coordinator state
        coordinator.active_actor = "non_existent_actor"

        # System should recover when turning on valid actor
        await boil_heater.on(80)
        assert coordinator.get_active_actor() == "boil_heater", "Should recover to valid actor"
        assert boil_heater.state == True, "Boil heater should be active"

    @pytest.mark.asyncio
    async def test_coordination_with_gpio_actors(self, coordination_harness):
        """Test coordination system integration with GPIO-based actors."""
        harness = coordination_harness["harness"]

        # Add GPIO actors to the coordination system
        gpio_heater1 = await harness.load_plugin(MockGPIOActor, "gpio_heater1", {"GPIO": 18, "Inverted": "No"})

        gpio_heater2 = await harness.load_plugin(MockGPIOActor, "gpio_heater2", {"GPIO": 19, "Inverted": "Yes"})

        # Wrap GPIO actors with coordination
        coord_gpio1 = await harness.load_plugin(
            MockOneAtATimeActor,
            "coord_gpio1",
            {"actor": "gpio_heater1", "OneAtATime group": 3},
        )

        coord_gpio2 = await harness.load_plugin(
            MockOneAtATimeActor,
            "coord_gpio2",
            {"actor": "gpio_heater2", "OneAtATime group": 3},
        )

        # Test coordination with GPIO state
        await coord_gpio1.on(100)
        assert coord_gpio1.state == True, "Coordinated GPIO actor 1 should be on"

        # Switch to second GPIO actor - should turn off first
        await coord_gpio2.on(80)
        assert coord_gpio2.state == True, "Coordinated GPIO actor 2 should be on"
        assert coord_gpio1.state == False, "Coordinated GPIO actor 1 should be off"

        # Test that coordination groups work independently
        coordinator = harness.cbpi._coordinators[3]
        assert coordinator.get_active_actor() == "coord_gpio2", "GPIO coordinator should track active actor"
        assert coordinator.get_actor_count() == 2, "GPIO coordinator should have 2 actors"

    @pytest.mark.asyncio
    async def test_multiple_coordination_groups(self, coordination_harness):
        """Test multiple independent coordination groups."""
        harness = coordination_harness["harness"]

        # Create actors in different groups
        group1_actor1 = coordination_harness["mash_heater"]  # group 1
        group2_actor1 = coordination_harness["separate_pump"]  # group 2

        # Add more actors to each group
        group1_actor2 = await harness.load_plugin(
            MockOneAtATimeActor,
            "group1_actor2",
            {"actor": "test_actor", "OneAtATime group": 1},
        )

        group2_actor2 = await harness.load_plugin(
            MockOneAtATimeActor,
            "group2_actor2",
            {"actor": "test_actor2", "OneAtATime group": 2},
        )

        # Test independent operation
        await group1_actor1.on(100)
        await group2_actor1.on(80)

        # Both should be active (different groups)
        assert group1_actor1.state == True, "Group 1 actor 1 should be active"
        assert group2_actor1.state == True, "Group 2 actor 1 should be active"

        # Switch within group 1 - should not affect group 2
        await group1_actor2.on(90)
        assert group1_actor2.state == True, "Group 1 actor 2 should be active"
        assert group1_actor1.state == False, "Group 1 actor 1 should be inactive"
        assert group2_actor1.state == True, "Group 2 actor 1 should remain active"

        # Switch within group 2 - should not affect group 1
        await group2_actor2.on(70)
        assert group2_actor2.state == True, "Group 2 actor 2 should be active"
        assert group2_actor1.state == False, "Group 2 actor 1 should be inactive"
        assert group1_actor2.state == True, "Group 1 actor 2 should remain active"
