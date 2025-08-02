"""
Integration tests for complete brewing workflow scenarios.

Tests end-to-end brewing processes involving coordinated operation of multiple
plugins including temperature control, display updates, mode switching, and
actor coordination throughout different brewing phases.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Import test fixtures
from tests.fixtures.cbpi_mock import (
    MockCBPi,
    MockCBPiActorBase,
    MockCBPiSensorBase,
    PluginTestHarness,
)
from tests.fixtures.hardware_mocks import (
    Mock7SegmentDisplay,
    MockLCDisplay,
    MockRPiGPIO,
    MockTemperatureSensor,
    create_brewmotron_hardware_setup,
)
from tests.fixtures.test_data import PluginConfigFactory

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class BrewingPhase(Enum):
    """Brewing process phases."""

    IDLE = "idle"
    MASH_HEAT = "mash_heat"
    MASH_HOLD = "mash_hold"
    SPARGE = "sparge"
    BOIL_HEAT = "boil_heat"
    BOIL_HOLD = "boil_hold"
    COOL_DOWN = "cool_down"
    FINISHED = "finished"


class MockBrewingController:
    """Mock brewing process controller for integration testing."""

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.current_phase = BrewingPhase.IDLE
        self.phase_start_time = None
        self.target_temperatures = {
            BrewingPhase.MASH_HEAT: 66.0,
            BrewingPhase.MASH_HOLD: 66.0,
            BrewingPhase.SPARGE: 78.0,
            BrewingPhase.BOIL_HEAT: 100.0,
            BrewingPhase.BOIL_HOLD: 100.0,
            BrewingPhase.COOL_DOWN: 20.0,
        }
        self.phase_durations = {  # in seconds for testing
            BrewingPhase.MASH_HEAT: 10,
            BrewingPhase.MASH_HOLD: 15,
            BrewingPhase.SPARGE: 8,
            BrewingPhase.BOIL_HEAT: 10,
            BrewingPhase.BOIL_HOLD: 12,
            BrewingPhase.COOL_DOWN: 8,
        }
        self.phase_history = []
        self._running = False
        self._task = None

    async def start_brewing(self):
        """Start the brewing process."""
        self._running = True
        self._task = asyncio.create_task(self._brewing_loop())
        await self._change_phase(BrewingPhase.MASH_HEAT)

    async def stop_brewing(self):
        """Stop the brewing process."""
        self._running = False
        if self._task:
            self._task.cancel()
        await self._change_phase(BrewingPhase.IDLE)

    async def _brewing_loop(self):
        """Main brewing process loop."""
        phase_sequence = [
            BrewingPhase.MASH_HEAT,
            BrewingPhase.MASH_HOLD,
            BrewingPhase.SPARGE,
            BrewingPhase.BOIL_HEAT,
            BrewingPhase.BOIL_HOLD,
            BrewingPhase.COOL_DOWN,
            BrewingPhase.FINISHED,
        ]

        try:
            for phase in phase_sequence:
                if not self._running:
                    break

                await self._change_phase(phase)

                if phase in self.phase_durations:
                    await asyncio.sleep(self.phase_durations[phase])

                # Check if we should advance based on conditions
                if not await self._should_advance_phase():
                    # Wait a bit more if conditions not met
                    await asyncio.sleep(2)

        except asyncio.CancelledError:
            pass

    async def _change_phase(self, new_phase: BrewingPhase):
        """Change to a new brewing phase."""
        old_phase = self.current_phase
        self.current_phase = new_phase
        self.phase_start_time = datetime.now()

        self.phase_history.append(
            {
                "phase": new_phase,
                "start_time": self.phase_start_time,
                "previous_phase": old_phase,
            }
        )

        # Configure system for new phase
        await self._configure_phase(new_phase)

        # Send notification
        await self.cbpi.notification.notify(
            "Phase Change", f"Brewing phase changed to {new_phase.value}", "info"
        )

    async def _configure_phase(self, phase: BrewingPhase):
        """Configure system for specific brewing phase."""
        if phase == BrewingPhase.IDLE:
            # Turn off all actors
            await self._turn_off_all_actors()

        elif phase in [BrewingPhase.MASH_HEAT, BrewingPhase.MASH_HOLD]:
            # Configure for mash heating
            await self.cbpi.actor.on("mash_heater", 100)
            await self.cbpi.actor.off("boil_heater")
            await self.cbpi.actor.off("pump")

        elif phase == BrewingPhase.SPARGE:
            # Configure for sparging
            await self.cbpi.actor.off("mash_heater")
            await self.cbpi.actor.on("sparge_heater", 80)
            await self.cbpi.actor.on("pump", 60)

        elif phase in [BrewingPhase.BOIL_HEAT, BrewingPhase.BOIL_HOLD]:
            # Configure for boiling
            await self.cbpi.actor.off("mash_heater")
            await self.cbpi.actor.on("boil_heater", 100)
            await self.cbpi.actor.off("pump")

        elif phase == BrewingPhase.COOL_DOWN:
            # Turn off heating, turn on cooling
            await self.cbpi.actor.off("boil_heater")
            await self.cbpi.actor.on("cooling_pump", 80)

        elif phase == BrewingPhase.FINISHED:
            await self._turn_off_all_actors()

    async def _turn_off_all_actors(self):
        """Turn off all actors."""
        actors = ["mash_heater", "boil_heater", "sparge_heater", "pump", "cooling_pump"]
        for actor in actors:
            try:
                await self.cbpi.actor.off(actor)
            except:
                pass  # Actor might not exist

    async def _should_advance_phase(self) -> bool:
        """Check if conditions are met to advance to next phase."""
        if self.current_phase in self.target_temperatures:
            target_temp = self.target_temperatures[self.current_phase]

            # Check primary temperature sensor
            try:
                current_temp = await self.cbpi.sensor.get_value("mash_temp")
                temp_reached = abs(current_temp - target_temp) < 2.0

                # For heating phases, also check minimum time
                if self.phase_start_time:
                    min_time_elapsed = (
                        datetime.now() - self.phase_start_time
                    ).total_seconds() > 3
                    return temp_reached and min_time_elapsed

                return temp_reached
            except:
                return True  # Advance if sensor not available

        return True  # No conditions, advance


class MockModeController:
    """Mock BMT-Key mode controller for integration testing."""

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.current_mode = "brew"
        self.mode_history = []
        self.gpio = MockRPiGPIO()
        self.key_pin = 21

        # Setup GPIO for key input
        self.gpio.setup(self.key_pin, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)

    async def initialize(self):
        """Initialize mode controller."""
        self.mode_history.append(
            {
                "mode": self.current_mode,
                "timestamp": datetime.now(),
                "source": "initialization",
            }
        )

    async def change_mode(self, new_mode: str):
        """Change system mode."""
        old_mode = self.current_mode
        self.current_mode = new_mode

        self.mode_history.append(
            {
                "mode": new_mode,
                "timestamp": datetime.now(),
                "source": "manual",
                "previous_mode": old_mode,
            }
        )

        # Configure system for new mode
        await self._configure_mode(new_mode)

        # Send notification
        await self.cbpi.notification.notify(
            "Mode Change", f"System mode changed to {new_mode}", "info"
        )

    async def _configure_mode(self, mode: str):
        """Configure system for specific mode."""
        if mode == "brew":
            # Configure for brewing mode
            await self.cbpi.config.set("BREWING_MODE", True)
            await self.cbpi.config.set("FERMENTATION_MODE", False)
            await self.cbpi.config.set("CLEANING_MODE", False)

        elif mode == "ferment":
            # Configure for fermentation mode
            await self.cbpi.config.set("BREWING_MODE", False)
            await self.cbpi.config.set("FERMENTATION_MODE", True)
            await self.cbpi.config.set("CLEANING_MODE", False)

        elif mode == "clean":
            # Configure for cleaning mode
            await self.cbpi.config.set("BREWING_MODE", False)
            await self.cbpi.config.set("FERMENTATION_MODE", False)
            await self.cbpi.config.set("CLEANING_MODE", True)

    def simulate_key_press(self):
        """Simulate physical key press."""
        # Simulate key press (pull pin low)
        self.gpio.simulate_input_change(self.key_pin, self.gpio.LOW)


class MockDisplayManager:
    """Mock display manager coordinating multiple displays."""

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.seg_displays = {}
        self.lcd_display = None
        self.display_mode = "brewing"
        self._running = False
        self._task = None

    async def initialize(self):
        """Initialize display manager."""
        # Setup 7-segment displays
        for addr in range(0x70, 0x74):
            self.seg_displays[addr] = Mock7SegmentDisplay(addr)

        # Setup LCD display
        self.lcd_display = MockLCDisplay(0x27, 20, 4)

        # Start update loop
        self._running = True
        self._task = asyncio.create_task(self._update_loop())

    async def shutdown(self):
        """Shutdown display manager."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _update_loop(self):
        """Main display update loop."""
        while self._running:
            try:
                await self._update_displays()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)  # Error recovery

    async def _update_displays(self):
        """Update all displays with current system state."""
        try:
            # Get sensor values
            mash_temp = await self.cbpi.sensor.get_value("mash_temp")
            boil_temp = await self.cbpi.sensor.get_value("boil_temp")

            # Update 7-segment displays
            if 0x70 in self.seg_displays:
                self.seg_displays[0x70].print(f"{mash_temp:.1f}")
                self.seg_displays[0x70].show()

            if 0x71 in self.seg_displays:
                self.seg_displays[0x71].print(f"{boil_temp:.1f}")
                self.seg_displays[0x71].show()

            # Update LCD display
            if self.lcd_display:
                self.lcd_display.clear()
                self.lcd_display.write_string("Brewmotron System", 0, 0)
                self.lcd_display.write_string("-" * 16, 0, 1)
                self.lcd_display.write_string(f"Mash: {mash_temp:.1f}C", 0, 2)
                self.lcd_display.write_string(f"Boil: {boil_temp:.1f}C", 0, 3)

        except Exception:
            pass  # Handle sensor errors gracefully

    def get_display_state(self):
        """Get current display state for testing."""
        return {
            "seg_displays": {
                addr: display.get_display_state()
                for addr, display in self.seg_displays.items()
            },
            "lcd_display": (
                self.lcd_display.get_display_state() if self.lcd_display else None
            ),
        }


class TestBrewingWorkflow:
    """Integration test suite for complete brewing workflows."""

    @pytest_asyncio.fixture
    async def brewing_system(self):
        """Create a complete brewing system for testing."""
        harness = PluginTestHarness()
        hardware = create_brewmotron_hardware_setup()

        # Register sensors and actors
        harness.cbpi.sensor.register_sensor(
            "mash_temp", {"id": "mash_temp", "type": "MockTemp"}
        )
        harness.cbpi.sensor.register_sensor(
            "boil_temp", {"id": "boil_temp", "type": "MockTemp"}
        )

        harness.cbpi.actor.register_actor(
            "mash_heater", {"id": "mash_heater", "type": "MockGPIO"}
        )
        harness.cbpi.actor.register_actor(
            "boil_heater", {"id": "boil_heater", "type": "MockGPIO"}
        )
        harness.cbpi.actor.register_actor(
            "sparge_heater", {"id": "sparge_heater", "type": "MockGPIO"}
        )
        harness.cbpi.actor.register_actor("pump", {"id": "pump", "type": "MockGPIO"})
        harness.cbpi.actor.register_actor(
            "cooling_pump", {"id": "cooling_pump", "type": "MockGPIO"}
        )

        # Initialize system components
        brewing_controller = MockBrewingController(harness.cbpi)
        mode_controller = MockModeController(harness.cbpi)
        display_manager = MockDisplayManager(harness.cbpi)

        await mode_controller.initialize()
        await display_manager.initialize()

        # Set initial sensor values
        await harness.cbpi.sensor.set_value("mash_temp", 20.0)
        await harness.cbpi.sensor.set_value("boil_temp", 20.0)

        yield {
            "harness": harness,
            "hardware": hardware,
            "brewing_controller": brewing_controller,
            "mode_controller": mode_controller,
            "display_manager": display_manager,
        }

        # Cleanup
        await brewing_controller.stop_brewing()
        await display_manager.shutdown()
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_complete_brewing_process(self, brewing_system):
        """Test complete brewing process from start to finish."""
        brewing_controller = brewing_system["brewing_controller"]
        harness = brewing_system["harness"]

        # Start brewing process
        await brewing_controller.start_brewing()

        # Simulate temperature responses during brewing
        asyncio.create_task(
            self._simulate_temperature_responses(harness, brewing_controller)
        )

        # Run brewing process
        await asyncio.sleep(25)  # Allow several phases to complete

        # Verify phase progression
        assert (
            len(brewing_controller.phase_history) >= 3
        ), f"Should have progressed through multiple phases, got {len(brewing_controller.phase_history)}"

        # Check that we progressed beyond initial phase
        phases = [entry["phase"] for entry in brewing_controller.phase_history]
        assert (
            BrewingPhase.MASH_HEAT in phases
        ), "Should have entered mash heating phase"
        assert (
            BrewingPhase.MASH_HOLD in phases or BrewingPhase.SPARGE in phases
        ), "Should have progressed to mash hold or sparge phase"

        # Verify actor coordination (only one active at a time)
        active_actors = []
        for actor_id in [
            "mash_heater",
            "boil_heater",
            "sparge_heater",
            "pump",
            "cooling_pump",
        ]:
            try:
                is_active = await harness.cbpi.actor.get_state(actor_id)
                if is_active:
                    active_actors.append(actor_id)
            except:
                pass

        # In OneAtATime system, should have at most one actor active
        assert (
            len(active_actors) <= 1
        ), f"Too many actors active simultaneously: {active_actors}"

        await brewing_controller.stop_brewing()

    async def _simulate_temperature_responses(self, harness, brewing_controller):
        """Simulate realistic temperature responses during brewing."""
        try:
            while brewing_controller._running:
                current_phase = brewing_controller.current_phase

                if current_phase in brewing_controller.target_temperatures:
                    target_temp = brewing_controller.target_temperatures[current_phase]

                    # Simulate gradual temperature change
                    current_mash = await harness.cbpi.sensor.get_value("mash_temp")
                    current_boil = await harness.cbpi.sensor.get_value("boil_temp")

                    # Move temperatures toward targets
                    if current_phase in [
                        BrewingPhase.MASH_HEAT,
                        BrewingPhase.MASH_HOLD,
                    ]:
                        new_mash = current_mash + (target_temp - current_mash) * 0.1
                        await harness.cbpi.sensor.set_value("mash_temp", new_mash)

                    elif current_phase in [
                        BrewingPhase.BOIL_HEAT,
                        BrewingPhase.BOIL_HOLD,
                    ]:
                        new_boil = current_boil + (target_temp - current_boil) * 0.08
                        await harness.cbpi.sensor.set_value("boil_temp", new_boil)

                    elif current_phase == BrewingPhase.SPARGE:
                        # Both temperatures move during sparge
                        new_mash = current_mash + (78.0 - current_mash) * 0.05
                        await harness.cbpi.sensor.set_value("mash_temp", new_mash)

                    elif current_phase == BrewingPhase.COOL_DOWN:
                        # Cooling phase - temperatures decrease
                        new_mash = max(20.0, current_mash - 2.0)
                        new_boil = max(20.0, current_boil - 3.0)
                        await harness.cbpi.sensor.set_value("mash_temp", new_mash)
                        await harness.cbpi.sensor.set_value("boil_temp", new_boil)

                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_mode_switching_during_brewing(self, brewing_system):
        """Test system behavior when switching modes during brewing."""
        brewing_controller = brewing_system["brewing_controller"]
        mode_controller = brewing_system["mode_controller"]
        harness = brewing_system["harness"]

        # Start in brew mode and begin brewing
        await mode_controller.change_mode("brew")
        await brewing_controller.start_brewing()

        # Let brewing run for a bit
        await asyncio.sleep(5)

        # Switch to cleaning mode (should affect system behavior)
        await mode_controller.change_mode("clean")

        # Verify mode change was recorded
        assert len(mode_controller.mode_history) >= 2, "Should have mode change history"
        assert mode_controller.current_mode == "clean", "Should be in cleaning mode"

        # Check configuration changes
        cleaning_mode = harness.cbpi.config.get("CLEANING_MODE")
        brewing_mode = harness.cbpi.config.get("BREWING_MODE")
        assert cleaning_mode == True, "Cleaning mode should be enabled"
        assert brewing_mode == False, "Brewing mode should be disabled"

        # Switch back to fermentation mode
        await mode_controller.change_mode("ferment")

        ferment_mode = harness.cbpi.config.get("FERMENTATION_MODE")
        assert ferment_mode == True, "Fermentation mode should be enabled"

        await brewing_controller.stop_brewing()

    @pytest.mark.asyncio
    async def test_display_coordination_during_brewing(self, brewing_system):
        """Test display updates during brewing process."""
        brewing_controller = brewing_system["brewing_controller"]
        display_manager = brewing_system["display_manager"]
        harness = brewing_system["harness"]

        # Set initial temperatures
        await harness.cbpi.sensor.set_value("mash_temp", 22.0)
        await harness.cbpi.sensor.set_value("boil_temp", 21.0)

        # Start brewing
        await brewing_controller.start_brewing()

        # Let system run and displays update
        await asyncio.sleep(3)

        # Check display states
        display_state = display_manager.get_display_state()

        # Verify 7-segment displays are showing values
        seg_displays = display_state["seg_displays"]
        assert len(seg_displays) > 0, "Should have 7-segment displays"

        # Check that displays are not showing default values
        for addr, display_info in seg_displays.items():
            assert display_info["display_buffer"] != [
                0,
                0,
                0,
                0,
            ], f"Display {addr} should show temperature data"

        # Verify LCD display content
        lcd_state = display_state["lcd_display"]
        assert lcd_state is not None, "Should have LCD display"

        lcd_content = lcd_state["content"]
        assert any(
            "Brewmotron" in line for line in lcd_content
        ), "LCD should show system name"
        assert any(
            ":" in line and "C" in line for line in lcd_content
        ), "LCD should show temperature data"

        # Change temperatures and verify display updates
        await harness.cbpi.sensor.set_value("mash_temp", 55.5)
        await harness.cbpi.sensor.set_value("boil_temp", 88.8)

        # Wait for display updates
        await asyncio.sleep(2)

        # Verify displays updated with new values
        updated_state = display_manager.get_display_state()
        updated_lcd = updated_state["lcd_display"]["content"]

        # Should contain updated temperature values
        temp_lines = [line for line in updated_lcd if ":" in line and "C" in line]
        assert len(temp_lines) >= 2, "Should show multiple temperature readings"

        await brewing_controller.stop_brewing()

    @pytest.mark.asyncio
    async def test_error_handling_during_brewing(self, brewing_system):
        """Test system behavior when errors occur during brewing."""
        brewing_controller = brewing_system["brewing_controller"]
        harness = brewing_system["harness"]

        # Start brewing
        await brewing_controller.start_brewing()
        await asyncio.sleep(2)

        # Simulate sensor failure
        original_get_value = harness.cbpi.sensor.get_value

        async def failing_sensor(sensor_id):
            if sensor_id == "mash_temp":
                raise Exception("Sensor disconnected")
            return await original_get_value(sensor_id)

        harness.cbpi.sensor.get_value = failing_sensor

        # Let system run with sensor failure
        await asyncio.sleep(3)

        # System should continue operating despite sensor failure
        assert brewing_controller._running, "Brewing controller should still be running"

        # Should have progressed phases (using fallback logic)
        assert (
            len(brewing_controller.phase_history) > 1
        ), "Should continue phase progression"

        # Restore sensor and continue
        harness.cbpi.sensor.get_value = original_get_value
        await asyncio.sleep(2)

        # System should recover
        mash_temp = await harness.cbpi.sensor.get_value("mash_temp")
        assert mash_temp is not None, "Sensor should be working again"

        await brewing_controller.stop_brewing()

    @pytest.mark.asyncio
    async def test_concurrent_system_operations(self, brewing_system):
        """Test system behavior with multiple concurrent operations."""
        brewing_controller = brewing_system["brewing_controller"]
        mode_controller = brewing_system["mode_controller"]
        display_manager = brewing_system["display_manager"]
        harness = brewing_system["harness"]

        # Start multiple concurrent operations
        tasks = [
            asyncio.create_task(brewing_controller.start_brewing()),
            asyncio.create_task(self._simulate_user_interactions(mode_controller)),
            asyncio.create_task(self._simulate_temperature_changes(harness)),
        ]

        # Let all operations run concurrently
        await asyncio.sleep(15)

        # Verify system stability
        assert brewing_controller._running, "Brewing controller should be stable"
        assert display_manager._running, "Display manager should be stable"

        # Check that all subsystems are functioning
        assert (
            len(brewing_controller.phase_history) > 0
        ), "Brewing should be progressing"
        assert len(mode_controller.mode_history) > 1, "Mode changes should be occurring"

        # Verify display updates are working
        display_state = display_manager.get_display_state()
        assert (
            display_state["lcd_display"] is not None
        ), "LCD display should be functioning"

        # Stop all operations
        await brewing_controller.stop_brewing()

        # Cancel remaining tasks
        for task in tasks:
            task.cancel()

    async def _simulate_user_interactions(self, mode_controller):
        """Simulate user mode changes during brewing."""
        try:
            modes = ["brew", "clean", "ferment", "brew"]
            for mode in modes:
                await asyncio.sleep(3)
                await mode_controller.change_mode(mode)
        except asyncio.CancelledError:
            pass

    async def _simulate_temperature_changes(self, harness):
        """Simulate external temperature fluctuations."""
        try:
            base_mash = 20.0
            base_boil = 20.0

            while True:
                # Add some realistic temperature variations
                import random

                mash_variation = random.uniform(-1.0, 1.0)
                boil_variation = random.uniform(-1.0, 1.0)

                await harness.cbpi.sensor.set_value(
                    "mash_temp", base_mash + mash_variation
                )
                await harness.cbpi.sensor.set_value(
                    "boil_temp", base_boil + boil_variation
                )

                base_mash += random.uniform(-0.5, 2.0)  # Gradual heating
                base_boil += random.uniform(-0.5, 1.8)

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_brewing_phase_timing_validation(self, brewing_system):
        """Test that brewing phases follow proper timing constraints."""
        brewing_controller = brewing_system["brewing_controller"]
        harness = brewing_system["harness"]

        # Configure fast temperature responses for timing test
        asyncio.create_task(
            self._fast_temperature_simulation(harness, brewing_controller)
        )

        # Start brewing and track timing
        start_time = datetime.now()
        await brewing_controller.start_brewing()

        # Wait for several phase transitions
        await asyncio.sleep(20)

        # Analyze phase timing
        phase_history = brewing_controller.phase_history
        assert len(phase_history) >= 3, "Should have multiple phase transitions"

        # Verify minimum phase durations
        for i in range(1, len(phase_history)):
            current_phase = phase_history[i]
            previous_phase = phase_history[i - 1]

            duration = (
                current_phase["start_time"] - previous_phase["start_time"]
            ).total_seconds()

            # Each phase should have minimum duration (accounting for test timing)
            assert (
                duration >= 1.0
            ), f"Phase {previous_phase['phase'].value} too short: {duration}s"
            assert (
                duration <= 15.0
            ), f"Phase {previous_phase['phase'].value} too long: {duration}s"

        # Verify logical phase sequence
        phase_names = [entry["phase"].value for entry in phase_history]

        # Should start with mash heating
        assert (
            phase_names[0] == "mash_heat"
        ), f"Should start with mash_heat, got {phase_names[0]}"

        # Should not have repeated phases (except potentially hold phases)
        non_hold_phases = [p for p in phase_names if "hold" not in p]
        assert len(non_hold_phases) == len(
            set(non_hold_phases)
        ), f"Should not repeat non-hold phases: {non_hold_phases}"

        await brewing_controller.stop_brewing()

    async def _fast_temperature_simulation(self, harness, brewing_controller):
        """Fast temperature simulation for timing tests."""
        try:
            while brewing_controller._running:
                current_phase = brewing_controller.current_phase

                if current_phase in brewing_controller.target_temperatures:
                    target_temp = brewing_controller.target_temperatures[current_phase]

                    # Rapid temperature changes for faster testing
                    if current_phase in [
                        BrewingPhase.MASH_HEAT,
                        BrewingPhase.MASH_HOLD,
                    ]:
                        await harness.cbpi.sensor.set_value(
                            "mash_temp", target_temp - 0.5
                        )
                    elif current_phase in [
                        BrewingPhase.BOIL_HEAT,
                        BrewingPhase.BOIL_HOLD,
                    ]:
                        await harness.cbpi.sensor.set_value(
                            "boil_temp", target_temp - 0.5
                        )
                    elif current_phase == BrewingPhase.SPARGE:
                        await harness.cbpi.sensor.set_value("mash_temp", 77.5)

                await asyncio.sleep(0.2)

        except asyncio.CancelledError:
            pass
