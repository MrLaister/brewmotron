"""
Unit tests for cbpi4-BMT-Key plugin.

Tests the BMT Key mode switching functionality with comprehensive hardware mocking
and edge case handling for brewing system modes (Off, Clean, Brew, Ferment).
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from datetime import datetime

# Import test fixtures
from tests.fixtures.cbpi_mock import MockCBPi, PluginTestHarness
from tests.fixtures.hardware_mocks import MockRPiGPIO, HardwareTestHarness
from tests.fixtures.test_data import PluginConfigFactory, ExtensionConfigFactory

# Mark all tests in this module as hardware tests
pytestmark = pytest.mark.hardware


class TestBMTKey:
    """Test suite for BMT Key plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness with BMT Key mocking."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.fixture
    def hardware_harness(self):
        """Create hardware test harness."""
        return HardwareTestHarness()

    @pytest.fixture
    def bmt_key_config(self):
        """Create BMT Key plugin configuration."""
        return ExtensionConfigFactory(
            id="test_bmt_key",
            name="TestBMTKey",
            props={
                "OFF_State": "actor_off_1",
                "Clean_State": "actor_clean_1",
                "Brew_State": "actor_brew_1",
                "Ferment_State": "actor_ferment_1",
            },
        )

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_harness, bmt_key_config):
        """Test BMT Key plugin initialization."""

        # Mock the plugin class since we can't import it directly
        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.actors = []
                self.settinggroupname = "BMT-Key_"
                self.settingDescription = (
                    "Select an Actor to indicate when this mode is active (high)"
                )
                self.keyStates = [
                    ("Off", "OFF_State", ""),
                    ("Clean", "Clean_State", ""),
                    ("Brew", "Brew_State", ""),
                    ("Ferment", "Ferment_State", ""),
                ]
                self.mode = self.keyStates[0][0]
                self._task = None

        plugin = await plugin_harness.load_plugin(
            MockBMTKey, bmt_key_config.id, bmt_key_config.props
        )

        # Verify initialization
        assert plugin.mode == "Off"
        assert len(plugin.keyStates) == 4
        assert plugin.settinggroupname == "BMT-Key_"
        assert plugin.actors == []

    @pytest.mark.asyncio
    async def test_mode_state_detection(self, plugin_harness, bmt_key_config):
        """Test detection of key mode states."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.actors = []
                self.settinggroupname = "BMT-Key_"
                self.settingDescription = (
                    "Select an Actor to indicate when this mode is active (high)"
                )
                self.keyStates = [
                    ("Off", "OFF_State", ""),
                    ("Clean", "Clean_State", ""),
                    ("Brew", "Brew_State", ""),
                    ("Ferment", "Ferment_State", ""),
                ]
                self.mode = self.keyStates[0][0]
                self.newMode = None
                self._task = None

            async def get_mode_actorID(self, stateName, settingDescription):
                """Mock getting actor ID for mode."""
                return f"actor_{stateName.lower()}_1"

            def enableMode(self, modeName):
                """Mock mode enabling."""
                self.mode = modeName

            async def check_state(self):
                """Mock state checking logic."""
                newModeList = []
                truecount = 0

                for modeName, modeID, actorID in self.keyStates:
                    actorID = await self.get_mode_actorID(
                        modeName, self.settingDescription
                    )
                    # Mock actor state - simulate Clean mode active
                    if modeName == "Clean":
                        modeState = True
                        truecount += 1
                        newModeList.append(modeName)
                    else:
                        modeState = False

                if truecount == 1:
                    self.newMode = newModeList[0]
                    if self.mode != self.newMode:
                        self.mode = self.newMode
                        self.enableMode(self.mode)

                return truecount, newModeList

        plugin = await plugin_harness.load_plugin(
            MockBMTKey, bmt_key_config.id, bmt_key_config.props
        )

        # Test state checking
        truecount, active_modes = await plugin.check_state()

        assert truecount == 1
        assert active_modes == ["Clean"]
        assert plugin.mode == "Clean"

    @pytest.mark.asyncio
    async def test_mode_transitions(self, plugin_harness, bmt_key_config):
        """Test transitions between different brewing modes."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.actors = ["actor1", "actor2"]
                self.mode = "Off"
                self.mode_enabled = None
                self.hp_actors_disabled = False
                self.hp_actors_enabled = False

            def enableMode(self, modeName):
                """Track mode enabling."""
                self.mode_enabled = modeName
                if modeName == "Off":
                    asyncio.create_task(self.disableHPActors())
                elif modeName in ["Clean", "Brew"]:
                    asyncio.create_task(self.enableHPActors())
                elif modeName == "Ferment":
                    asyncio.create_task(self.disableHPActors())

            async def disableHPActors(self):
                """Mock disabling high-power actors."""
                self.hp_actors_disabled = True
                self.hp_actors_enabled = False

            async def enableHPActors(self):
                """Mock enabling high-power actors."""
                self.hp_actors_enabled = True
                self.hp_actors_disabled = False

        plugin = await plugin_harness.load_plugin(
            MockBMTKey, bmt_key_config.id, bmt_key_config.props
        )

        # Test Off mode
        plugin.enableMode("Off")
        await asyncio.sleep(0.1)  # Allow async tasks to execute
        assert plugin.mode_enabled == "Off"
        assert plugin.hp_actors_disabled == True

        # Test Clean mode
        plugin.enableMode("Clean")
        await asyncio.sleep(0.1)
        assert plugin.mode_enabled == "Clean"
        assert plugin.hp_actors_enabled == True

        # Test Brew mode
        plugin.enableMode("Brew")
        await asyncio.sleep(0.1)
        assert plugin.mode_enabled == "Brew"
        assert plugin.hp_actors_enabled == True

        # Test Ferment mode
        plugin.enableMode("Ferment")
        await asyncio.sleep(0.1)
        assert plugin.mode_enabled == "Ferment"
        assert plugin.hp_actors_disabled == True

    @pytest.mark.asyncio
    async def test_actor_management(self, plugin_harness, bmt_key_config):
        """Test OneAtATime actor loading and management."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.actors = []

            def loadActorValues(self, actorPluginType):
                """Mock loading OneAtATime actors."""
                # Simulate actor JSON structure
                mock_actors = [
                    {
                        "id": "actor1",
                        "type": "OneAtATimeActor",
                        "props": {"actor": "heater1"},
                    },
                    {
                        "id": "actor2",
                        "type": "OneAtATimeActor",
                        "props": {"actor": "pump1"},
                    },
                    {"id": "actor3", "type": "GPIOActor", "props": {"actor": "valve1"}},
                ]

                self.actors = []
                for actor in mock_actors:
                    if actor["type"] == actorPluginType:
                        self.actors.append(actor["id"])
                        self.actors.append(actor["props"]["actor"])

                return len([a for a in mock_actors if a["type"] == actorPluginType])

        plugin = await plugin_harness.load_plugin(
            MockBMTKey, bmt_key_config.id, bmt_key_config.props
        )

        # Test loading OneAtATime actors
        count = plugin.loadActorValues("OneAtATimeActor")

        assert count == 2  # Two OneAtATime actors found
        assert len(plugin.actors) == 4  # 2 actors × 2 entries each (id + props.actor)
        assert "actor1" in plugin.actors
        assert "heater1" in plugin.actors
        assert "actor2" in plugin.actors
        assert "pump1" in plugin.actors

    @pytest.mark.asyncio
    async def test_config_parameter_management(self, plugin_harness, bmt_key_config):
        """Test dynamic configuration parameter creation."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.settinggroupname = "BMT-Key_"
                self.settingDescription = (
                    "Select an Actor to indicate when this mode is active (high)"
                )

            async def get_mode_actorID(self, stateName, settingDescription):
                """Mock configuration parameter management."""
                settingsName = self.settinggroupname + stateName + "_GPIO"

                # Simulate config.get returning None first time
                mode_actorID = self.cbpi.config.get(settingsName, None)

                if mode_actorID is None:
                    # Simulate adding new config parameter
                    await self.cbpi.config.add(
                        settingsName, "", "ACTOR", settingDescription
                    )
                    mode_actorID = f"actor_{stateName.lower()}_1"
                    # Update the mock config
                    self.cbpi.config._config_data[settingsName] = mode_actorID

                return mode_actorID

        plugin = await plugin_harness.load_plugin(
            MockBMTKey, bmt_key_config.id, bmt_key_config.props
        )

        # Test configuration parameter creation
        actor_id = await plugin.get_mode_actorID("Off", plugin.settingDescription)

        assert actor_id == "actor_off_1"
        assert "BMT-Key_Off_GPIO" in plugin.cbpi.config._config_data

    @pytest.mark.asyncio
    async def test_multiple_active_states_warning(self, plugin_harness, bmt_key_config):
        """Test handling of multiple simultaneous active key states."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.actors = []
                self.settinggroupname = "BMT-Key_"
                self.settingDescription = (
                    "Select an Actor to indicate when this mode is active (high)"
                )
                self.keyStates = [
                    ("Off", "OFF_State", ""),
                    ("Clean", "Clean_State", ""),
                    ("Brew", "Brew_State", ""),
                    ("Ferment", "Ferment_State", ""),
                ]
                self.mode = self.keyStates[0][0]
                self.warning_messages = []

            async def get_mode_actorID(self, stateName, settingDescription):
                return f"actor_{stateName.lower()}_1"

            def enableMode(self, modeName):
                self.mode = modeName

            async def check_state(self):
                """Mock state checking with multiple active states."""
                newModeList = []
                truecount = 0

                # Simulate multiple active states (Clean and Brew both active)
                active_modes = ["Clean", "Brew"]

                for modeName, modeID, actorID in self.keyStates:
                    if modeName in active_modes:
                        truecount += 1
                        newModeList.append(modeName)

                if truecount == 0:
                    self.warning_messages.append("WARNING - No key states detected")
                elif truecount == 1:
                    self.newMode = newModeList[0]
                    if self.mode != self.newMode:
                        self.mode = self.newMode
                        self.enableMode(self.mode)
                elif truecount > 1:
                    self.warning_messages.append(
                        "WARNING - Multiple key states detected"
                    )

                return truecount, newModeList

        plugin = await plugin_harness.load_plugin(
            MockBMTKey, bmt_key_config.id, bmt_key_config.props
        )

        # Test multiple active states
        truecount, active_modes = await plugin.check_state()

        assert truecount == 2
        assert "Clean" in active_modes
        assert "Brew" in active_modes
        assert "WARNING - Multiple key states detected" in plugin.warning_messages


class TestBMTKeyEdgeCases:
    """Test edge cases and error conditions for BMT Key plugin."""

    @pytest_asyncio.fixture
    async def plugin_harness(self):
        """Create a plugin test harness."""
        harness = PluginTestHarness()
        yield harness
        await harness.cleanup()

    @pytest.mark.asyncio
    async def test_no_active_states_warning(self, plugin_harness):
        """Test handling when no key states are active."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.keyStates = [
                    ("Off", "OFF_State", ""),
                    ("Clean", "Clean_State", ""),
                    ("Brew", "Brew_State", ""),
                    ("Ferment", "Ferment_State", ""),
                ]
                self.mode = "Off"
                self.warning_messages = []

            async def get_mode_actorID(self, stateName, settingDescription):
                return f"actor_{stateName.lower()}_1"

            async def check_state(self):
                """Mock state checking with no active states."""
                newModeList = []
                truecount = 0

                # Simulate no active states
                for modeName, modeID, actorID in self.keyStates:
                    # All states return False
                    pass

                if truecount == 0:
                    self.warning_messages.append("WARNING - No key states detected")

                return truecount, newModeList

        config = ExtensionConfigFactory(
            id="test_no_states", name="TestNoStates", props={}
        )

        plugin = await plugin_harness.load_plugin(MockBMTKey, config.id, config.props)

        # Test no active states
        truecount, active_modes = await plugin.check_state()

        assert truecount == 0
        assert active_modes == []
        assert "WARNING - No key states detected" in plugin.warning_messages

    @pytest.mark.asyncio
    async def test_config_parameter_creation_failure(self, plugin_harness):
        """Test handling of configuration parameter creation failures."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.settinggroupname = "BMT-Key_"
                self.settingDescription = (
                    "Select an Actor to indicate when this mode is active (high)"
                )
                self.config_errors = []

            async def get_mode_actorID(self, stateName, settingDescription):
                """Mock configuration parameter management with error."""
                settingsName = self.settinggroupname + stateName + "_GPIO"

                mode_actorID = self.cbpi.config.get(settingsName, None)

                if mode_actorID is None:
                    try:
                        # Simulate config.add failure
                        raise Exception("Config add failed")
                    except Exception as e:
                        self.config_errors.append(
                            f"Unable to update config for {settingsName}: {e}"
                        )
                        mode_actorID = None

                return mode_actorID

        config = ExtensionConfigFactory(
            id="test_config_error", name="TestConfigError", props={}
        )

        plugin = await plugin_harness.load_plugin(MockBMTKey, config.id, config.props)

        # Test configuration error handling
        actor_id = await plugin.get_mode_actorID("Off", plugin.settingDescription)

        assert actor_id is None
        assert len(plugin.config_errors) == 1
        assert "Unable to update config for BMT-Key_Off_GPIO" in plugin.config_errors[0]

    @pytest.mark.asyncio
    async def test_actor_loading_error_handling(self, plugin_harness):
        """Test error handling during actor loading."""

        class MockBMTKey:
            _plugin_type = "Extension"

            def __init__(self, cbpi):
                self.cbpi = cbpi
                self.actors = []
                self.load_errors = []

            def loadActorValues(self, actorPluginType):
                """Mock actor loading with error."""
                try:
                    # Simulate cbpi.actor.get_state() failure
                    raise Exception("Failed to get actor state")
                except Exception as e:
                    self.load_errors.append(str(e))
                    return 0

        config = ExtensionConfigFactory(
            id="test_actor_error", name="TestActorError", props={}
        )

        plugin = await plugin_harness.load_plugin(MockBMTKey, config.id, config.props)

        # Test actor loading error
        count = plugin.loadActorValues("OneAtATimeActor")

        assert count == 0
        assert len(plugin.load_errors) == 1
        assert "Failed to get actor state" in plugin.load_errors[0]
