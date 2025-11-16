"""
Integration tests for GPIO resource management and coordination.

Tests multiple plugins sharing GPIO resources, ensuring proper pin allocation,
conflict detection, and coordinated access to GPIO pins across different
plugin types (actors, sensors, inputs).
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, MockCBPiActorBase, PluginTestHarness
from tests.fixtures.hardware_mocks import HardwareTestHarness, MockRPiGPIO
from tests.fixtures.test_data import GPIOActorConfigFactory, PluginConfigFactory

# Mark all tests in this module as integration tests
# PHASE 2: Temporarily skipped during cache handler conversion
# These plugin integration tests will be re-enabled after plugins are refactored to use cache handler
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skip(reason="Phase 2: Plugin refactoring - re-enable after cache handler integration"),
]


class MockGPIOActor(MockCBPiActorBase):
    """Mock GPIO actor plugin for testing."""

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.gpio_pin = int(props.get("GPIO", 18))
        self.inverted = props.get("Inverted", "No") == "Yes"
        self.gpio = cbpi._gpio if hasattr(cbpi, "_gpio") else MockRPiGPIO()
        self.setup_complete = False

    async def on_start(self):
        """Setup GPIO pin."""
        try:
            self.gpio.setup(self.gpio_pin, self.gpio.OUT)
            self.setup_complete = True
        except Exception as e:
            # Handle GPIO conflicts
            self.setup_complete = False
            raise Exception(f"GPIO pin {self.gpio_pin} setup failed: {e}")

    async def on(self, power=None):
        """Turn GPIO actor on."""
        if not self.setup_complete:
            return False

        await super().on(power)
        output_value = self.gpio.LOW if self.inverted else self.gpio.HIGH
        self.gpio.output(self.gpio_pin, output_value)
        return True

    async def off(self):
        """Turn GPIO actor off."""
        if not self.setup_complete:
            return False

        await super().off()
        output_value = self.gpio.HIGH if self.inverted else self.gpio.LOW
        self.gpio.output(self.gpio_pin, output_value)
        return True

    async def on_stop(self):
        """Cleanup GPIO resources."""
        if self.setup_complete:
            self.gpio.cleanup(self.gpio_pin)


class MockGPIOInput:
    """Mock GPIO input plugin for testing."""

    def __init__(self, cbpi, id, props):
        self.cbpi = cbpi
        self.id = id
        self.props = props
        self.gpio_pin = int(props.get("GPIO", 19))
        self.pull_up_down = props.get("Pull", "PUD_UP")
        self.gpio = cbpi._gpio if hasattr(cbpi, "_gpio") else MockRPiGPIO()
        self.setup_complete = False
        self.current_state = False
        self.callback = None
        self._task = None

    async def on_start(self):
        """Setup GPIO input pin."""
        try:
            pull_mode = getattr(self.gpio, self.pull_up_down, self.gpio.PUD_UP)
            self.gpio.setup(self.gpio_pin, self.gpio.IN, pull_up_down=pull_mode)
            self.setup_complete = True

            # Start monitoring loop
            self._task = asyncio.create_task(self._monitor_input())
        except Exception as e:
            self.setup_complete = False
            raise Exception(f"GPIO input pin {self.gpio_pin} setup failed: {e}")

    async def on_stop(self):
        """Cleanup GPIO input resources."""
        if self._task:
            self._task.cancel()

        if self.setup_complete:
            self.gpio.cleanup(self.gpio_pin)

    async def _monitor_input(self):
        """Monitor GPIO input for state changes."""
        try:
            while self.setup_complete:
                new_state = bool(self.gpio.input(self.gpio_pin))

                if new_state != self.current_state:
                    self.current_state = new_state

                    if self.callback:
                        await self.callback(self.id, new_state)

                await asyncio.sleep(0.1)  # Poll rate
        except asyncio.CancelledError:
            pass

    def set_callback(self, callback):
        """Set state change callback."""
        self.callback = callback

    def get_state(self):
        """Get current input state."""
        return self.current_state


class MockAlwaysOnGPIO(MockCBPiActorBase):
    """Mock AlwaysON GPIO plugin for testing."""

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.gpio_pin = int(props.get("GPIO", 20))
        self.active_state = props.get("ActiveState", "HIGH")
        self.gpio = cbpi._gpio if hasattr(cbpi, "_gpio") else MockRPiGPIO()
        self.setup_complete = False
        self.always_on = True

    async def on_start(self):
        """Setup and activate always-on GPIO."""
        try:
            self.gpio.setup(self.gpio_pin, self.gpio.OUT)
            self.setup_complete = True

            # Turn on immediately (always-on behavior)
            await self.on()
        except Exception as e:
            self.setup_complete = False
            raise Exception(f"Always-on GPIO pin {self.gpio_pin} setup failed: {e}")

    async def on(self, power=None):
        """Turn always-on GPIO on."""
        if not self.setup_complete:
            return False

        await super().on(power)
        output_value = self.gpio.HIGH if self.active_state == "HIGH" else self.gpio.LOW
        self.gpio.output(self.gpio_pin, output_value)
        return True

    async def off(self):
        """Always-on GPIO cannot be turned off normally."""
        # Always-on GPIO stays on unless explicitly forced
        return False

    async def force_off(self):
        """Force always-on GPIO off (for testing/emergency)."""
        if not self.setup_complete:
            return False

        await super().off()
        output_value = self.gpio.LOW if self.active_state == "HIGH" else self.gpio.HIGH
        self.gpio.output(self.gpio_pin, output_value)
        return True

    async def on_stop(self):
        """Cleanup always-on GPIO resources."""
        if self.setup_complete:
            await self.force_off()
            self.gpio.cleanup(self.gpio_pin)


class GPIOResourceManager:
    """GPIO resource manager for coordinating pin usage."""

    def __init__(self, gpio):
        self.gpio = gpio
        self.allocated_pins = {}  # pin -> (plugin_id, plugin_type, mode)
        self.pin_conflicts = []

    def allocate_pin(self, pin, plugin_id, plugin_type, mode):
        """Allocate a GPIO pin to a plugin."""
        if pin in self.allocated_pins:
            existing = self.allocated_pins[pin]
            conflict = {
                "pin": pin,
                "existing": existing,
                "requesting": (plugin_id, plugin_type, mode),
                "timestamp": datetime.now(),
            }
            self.pin_conflicts.append(conflict)
            raise ValueError(f"GPIO pin {pin} already allocated to {existing[0]} ({existing[1]})")

        self.allocated_pins[pin] = (plugin_id, plugin_type, mode)
        return True

    def release_pin(self, pin, plugin_id):
        """Release a GPIO pin from a plugin."""
        if pin in self.allocated_pins:
            allocated_plugin, _, _ = self.allocated_pins[pin]
            if allocated_plugin == plugin_id:
                del self.allocated_pins[pin]
                return True
            else:
                raise ValueError(f"Pin {pin} not allocated to {plugin_id}")

        return False

    def get_pin_allocation(self, pin):
        """Get current allocation for a pin."""
        return self.allocated_pins.get(pin)

    def get_allocated_pins(self):
        """Get all allocated pins."""
        return self.allocated_pins.copy()

    def get_conflicts(self):
        """Get all recorded pin conflicts."""
        return self.pin_conflicts.copy()

    def check_pin_compatibility(self, pin, mode1, mode2):
        """Check if two modes are compatible on the same pin."""
        # Two outputs cannot share a pin
        if mode1 == "OUT" and mode2 == "OUT":
            return False

        # Input and output generally cannot share a pin
        if (mode1 == "IN" and mode2 == "OUT") or (mode1 == "OUT" and mode2 == "IN"):
            return False

        # Two inputs might be compatible in some cases
        if mode1 == "IN" and mode2 == "IN":
            return True  # Depends on specific use case

        return True


class TestGPIOResourceManagement:
    """Integration test suite for GPIO resource management."""

    @pytest_asyncio.fixture
    async def gpio_system(self):
        """Create a GPIO system with resource management."""
        harness = PluginTestHarness()

        # Create shared GPIO instance
        gpio = MockRPiGPIO()
        harness.cbpi._gpio = gpio

        # Create GPIO resource manager
        resource_manager = GPIOResourceManager(gpio)
        harness.cbpi._gpio_manager = resource_manager

        yield {"harness": harness, "gpio": gpio, "resource_manager": resource_manager}

        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_basic_gpio_allocation(self, gpio_system):
        """Test basic GPIO pin allocation and release."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create GPIO actors on different pins
        actor1 = await harness.load_plugin(MockGPIOActor, "heater1", {"GPIO": 18, "Inverted": "No"})

        actor2 = await harness.load_plugin(MockGPIOActor, "heater2", {"GPIO": 19, "Inverted": "Yes"})

        # Manually register pin allocations (simulating resource manager)
        resource_manager.allocate_pin(18, "heater1", "actor", "OUT")
        resource_manager.allocate_pin(19, "heater2", "actor", "OUT")

        # Verify pins are allocated
        assert resource_manager.get_pin_allocation(18) == ("heater1", "actor", "OUT")
        assert resource_manager.get_pin_allocation(19) == ("heater2", "actor", "OUT")

        # Test actor operation
        assert await actor1.on(100) == True, "Actor 1 should turn on successfully"
        assert await actor2.on(80) == True, "Actor 2 should turn on successfully"

        # Verify GPIO states
        assert gpio_system["gpio"].input(18) == gpio_system["gpio"].HIGH, "Pin 18 should be HIGH"
        assert gpio_system["gpio"].input(19) == gpio_system["gpio"].LOW, "Pin 19 should be LOW (inverted)"

        # Release pins
        resource_manager.release_pin(18, "heater1")
        resource_manager.release_pin(19, "heater2")

        assert resource_manager.get_pin_allocation(18) is None, "Pin 18 should be released"
        assert resource_manager.get_pin_allocation(19) is None, "Pin 19 should be released"

    @pytest.mark.asyncio
    async def test_gpio_pin_conflicts(self, gpio_system):
        """Test GPIO pin conflict detection and handling."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create first actor on pin 18
        actor1 = await harness.load_plugin(MockGPIOActor, "heater1", {"GPIO": 18, "Inverted": "No"})

        # Allocate pin to first actor
        resource_manager.allocate_pin(18, "heater1", "actor", "OUT")

        # Try to create second actor on same pin
        actor2 = await harness.load_plugin(MockGPIOActor, "heater2", {"GPIO": 18, "Inverted": "Yes"})  # Same pin!

        # Attempt to allocate same pin should cause conflict
        with pytest.raises(ValueError, match="already allocated"):
            resource_manager.allocate_pin(18, "heater2", "actor", "OUT")

        # Verify conflict was recorded
        conflicts = resource_manager.get_conflicts()
        assert len(conflicts) == 1, "Should have recorded one conflict"

        conflict = conflicts[0]
        assert conflict["pin"] == 18, "Conflict should be on pin 18"
        assert conflict["existing"][0] == "heater1", "Existing allocation should be heater1"
        assert conflict["requesting"][0] == "heater2", "Requesting allocation should be heater2"

    @pytest.mark.asyncio
    async def test_mixed_gpio_plugin_types(self, gpio_system):
        """Test coordination between different GPIO plugin types."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create different types of GPIO plugins
        actor = await harness.load_plugin(MockGPIOActor, "pump", {"GPIO": 18, "Inverted": "No"})

        gpio_input = MockGPIOInput(harness.cbpi, "button", {"GPIO": 19, "Pull": "PUD_UP"})

        always_on = await harness.load_plugin(MockAlwaysOnGPIO, "indicator_led", {"GPIO": 20, "ActiveState": "HIGH"})

        # Allocate pins for different plugin types
        resource_manager.allocate_pin(18, "pump", "actor", "OUT")
        resource_manager.allocate_pin(19, "button", "input", "IN")
        resource_manager.allocate_pin(20, "indicator_led", "always_on", "OUT")

        # Start GPIO input
        await gpio_input.on_start()

        # Verify all plugins can operate independently
        assert await actor.on(100) == True, "Actor should turn on"
        assert gpio_input.setup_complete == True, "Input should be set up"
        assert always_on.state == True, "Always-on should be active"

        # Verify GPIO states
        assert gpio_system["gpio"].input(18) == gpio_system["gpio"].HIGH, "Actor pin should be HIGH"
        assert gpio_system["gpio"].input(20) == gpio_system["gpio"].HIGH, "Always-on pin should be HIGH"

        # Test input monitoring
        input_states = []

        async def input_callback(input_id, state):
            input_states.append((input_id, state))

        gpio_input.set_callback(input_callback)

        # Simulate input change
        gpio_system["gpio"].simulate_input_change(19, gpio_system["gpio"].LOW)
        await asyncio.sleep(0.2)  # Allow monitoring loop to detect change

        assert len(input_states) > 0, "Input change should be detected"

        # Cleanup
        await gpio_input.on_stop()

    @pytest.mark.asyncio
    async def test_gpio_resource_cleanup(self, gpio_system):
        """Test proper GPIO resource cleanup when plugins stop."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create multiple GPIO plugins
        plugins = []
        pins = [18, 19, 20, 21]

        for i, pin in enumerate(pins):
            plugin = await harness.load_plugin(MockGPIOActor, f"actor_{i}", {"GPIO": pin, "Inverted": "No"})
            plugins.append(plugin)
            resource_manager.allocate_pin(pin, f"actor_{i}", "actor", "OUT")

        # Verify all pins are allocated
        allocated_pins = resource_manager.get_allocated_pins()
        assert len(allocated_pins) == 4, "Should have 4 allocated pins"

        # Turn on all actors
        for plugin in plugins:
            assert await plugin.on(100) == True, f"Plugin {plugin.id} should turn on"

        # Stop plugins one by one and verify cleanup
        for i, plugin in enumerate(plugins):
            await plugin.on_stop()
            resource_manager.release_pin(pins[i], plugin.id)

            # Verify pin is released
            assert resource_manager.get_pin_allocation(pins[i]) is None, f"Pin {pins[i]} should be released after plugin stop"

        # Verify all pins are cleaned up
        final_allocated = resource_manager.get_allocated_pins()
        assert len(final_allocated) == 0, "All pins should be released"

    @pytest.mark.asyncio
    async def test_gpio_state_coordination(self, gpio_system):
        """Test GPIO state coordination between plugins."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create coordinated actors (OneAtATime behavior)
        actor1 = await harness.load_plugin(MockGPIOActor, "heater1", {"GPIO": 18, "Inverted": "No"})

        actor2 = await harness.load_plugin(MockGPIOActor, "heater2", {"GPIO": 19, "Inverted": "No"})

        always_on = await harness.load_plugin(MockAlwaysOnGPIO, "safety_led", {"GPIO": 20, "ActiveState": "HIGH"})

        # Allocate pins
        resource_manager.allocate_pin(18, "heater1", "actor", "OUT")
        resource_manager.allocate_pin(19, "heater2", "actor", "OUT")
        resource_manager.allocate_pin(20, "safety_led", "always_on", "OUT")

        # Test coordinated operation
        await actor1.on(100)
        assert gpio_system["gpio"].input(18) == gpio_system["gpio"].HIGH, "Heater 1 should be on"
        assert gpio_system["gpio"].input(20) == gpio_system["gpio"].HIGH, "Safety LED should always be on"

        # Switch to second heater (coordination logic would turn off first)
        await actor1.off()
        await actor2.on(80)

        assert gpio_system["gpio"].input(18) == gpio_system["gpio"].LOW, "Heater 1 should be off"
        assert gpio_system["gpio"].input(19) == gpio_system["gpio"].HIGH, "Heater 2 should be on"
        assert gpio_system["gpio"].input(20) == gpio_system["gpio"].HIGH, "Safety LED should remain on"

        # Try to turn off always-on GPIO (should fail)
        result = await always_on.off()
        assert result == False, "Always-on GPIO should not turn off normally"
        assert gpio_system["gpio"].input(20) == gpio_system["gpio"].HIGH, "Safety LED should stay on"

        # Force off should work
        result = await always_on.force_off()
        assert result == True, "Force off should work"
        assert gpio_system["gpio"].input(20) == gpio_system["gpio"].LOW, "Safety LED should be forced off"

    @pytest.mark.asyncio
    async def test_gpio_error_recovery(self, gpio_system):
        """Test GPIO error handling and recovery."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]
        gpio = gpio_system["gpio"]

        # Create actor
        actor = await harness.load_plugin(MockGPIOActor, "test_actor", {"GPIO": 18, "Inverted": "No"})

        resource_manager.allocate_pin(18, "test_actor", "actor", "OUT")

        # Normal operation
        assert await actor.on(100) == True, "Actor should turn on normally"

        # Simulate GPIO error by corrupting GPIO state
        original_output = gpio.output

        def failing_output(pin, value):
            if pin == 18:
                raise RuntimeError("GPIO hardware error")
            return original_output(pin, value)

        gpio.output = failing_output

        # Actor operation should handle error gracefully
        try:
            await actor.off()
            await actor.on(50)
        except Exception as e:
            # GPIO errors should be caught and handled
            assert "GPIO hardware error" in str(e)

        # Restore GPIO and verify recovery
        gpio.output = original_output

        # Should be able to operate normally again
        assert await actor.on(75) == True, "Actor should recover from GPIO error"
        assert gpio.input(18) == gpio.HIGH, "GPIO should be working again"

    @pytest.mark.asyncio
    async def test_concurrent_gpio_access(self, gpio_system):
        """Test concurrent GPIO access from multiple plugins."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create multiple actors on different pins
        actors = []
        pins = [18, 19, 20, 21, 22]

        for i, pin in enumerate(pins):
            actor = await harness.load_plugin(MockGPIOActor, f"concurrent_actor_{i}", {"GPIO": pin, "Inverted": "No"})
            actors.append(actor)
            resource_manager.allocate_pin(pin, f"concurrent_actor_{i}", "actor", "OUT")

        # Create concurrent tasks to operate all actors
        async def operate_actor(actor, cycles=10):
            for i in range(cycles):
                await actor.on(50 + i * 5)
                await asyncio.sleep(0.1)
                await actor.off()
                await asyncio.sleep(0.1)

        # Run all actors concurrently
        tasks = [asyncio.create_task(operate_actor(actor)) for actor in actors]

        # Wait for all concurrent operations to complete
        await asyncio.gather(*tasks)

        # Verify all actors completed operations successfully
        for i, actor in enumerate(actors):
            # All actors should be in off state after operations
            assert actor.state == False, f"Actor {i} should be off after operations"

            # Verify GPIO pins are in correct state
            expected_value = gpio_system["gpio"].LOW  # Should be off
            actual_value = gpio_system["gpio"].input(pins[i])
            assert actual_value == expected_value, f"Pin {pins[i]} should be {expected_value}, got {actual_value}"

    @pytest.mark.asyncio
    async def test_gpio_pin_sharing_compatibility(self, gpio_system):
        """Test GPIO pin sharing compatibility checks."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Test incompatible sharing (two outputs on same pin)
        compatibility = resource_manager.check_pin_compatibility(18, "OUT", "OUT")
        assert compatibility == False, "Two outputs should not be compatible"

        # Test incompatible sharing (input and output on same pin)
        compatibility = resource_manager.check_pin_compatibility(18, "IN", "OUT")
        assert compatibility == False, "Input and output should not be compatible"

        # Test potentially compatible sharing (two inputs)
        compatibility = resource_manager.check_pin_compatibility(18, "IN", "IN")
        assert compatibility == True, "Two inputs might be compatible"

        # Verify resource manager enforces compatibility
        resource_manager.allocate_pin(18, "plugin1", "actor", "OUT")

        # Should fail to allocate same pin for output
        with pytest.raises(ValueError):
            resource_manager.allocate_pin(18, "plugin2", "actor", "OUT")

    @pytest.mark.asyncio
    async def test_gpio_system_stress_test(self, gpio_system):
        """Stress test GPIO system with rapid operations."""
        harness = gpio_system["harness"]
        resource_manager = gpio_system["resource_manager"]

        # Create actor for stress testing
        actor = await harness.load_plugin(MockGPIOActor, "stress_actor", {"GPIO": 18, "Inverted": "No"})

        resource_manager.allocate_pin(18, "stress_actor", "actor", "OUT")

        # Perform rapid on/off cycles
        operations = 100
        start_time = datetime.now()

        for i in range(operations):
            await actor.on(i % 100)
            await actor.off()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Verify performance (should complete operations reasonably quickly)
        assert duration < 10.0, f"Stress test took too long: {duration}s"

        # Verify final state is consistent
        assert actor.state == False, "Actor should be off after stress test"
        assert gpio_system["gpio"].input(18) == gpio_system["gpio"].LOW, "GPIO should be LOW"

        # Verify GPIO is still functional after stress test
        assert await actor.on(100) == True, "Actor should still work after stress test"
        assert gpio_system["gpio"].input(18) == gpio_system["gpio"].HIGH, "GPIO should respond correctly"
