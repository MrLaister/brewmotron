"""
CraftBeerPi4 Mock Framework

Comprehensive mocking framework for CraftBeerPi4 API components to enable
isolated testing of Brewmotron plugins without requiring a full CBPI installation.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import async_timeout

logger = logging.getLogger(__name__)

# =============================================================================
# Core CBPI API Mocks
# =============================================================================


class MockCBPiConfig:
    """Mock CraftBeerPi4 configuration system."""

    def __init__(self):
        self._config_data = {
            # Default CBPI configuration values
            "SENSOR_LOG_BACKUP_COUNT": 3,
            "SENSOR_LOG_MAX_BYTES": 100000,
            "ACTOR_LOG_BACKUP_COUNT": 3,
            "steps_cooldown_sensor": None,
            "steps_cooldown_actor": None,
            "DASHBOARD_NUMBER": 1,
            "INFLUXDB": False,
            "INFLUXDB_URL": "http://localhost:8086",
            "INFLUXDB_BUCKET": "cbpi4",
            "INFLUXDB_ORG": "cbpi",
            "INFLUXDB_TOKEN": "",
            "INFLUXDB_MEASUREMENT": "cbpi4",
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config_data.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._config_data[key] = value
        logger.debug(f"Config set: {key} = {value}")

    async def add(
        self,
        key: str,
        value: Any,
        type: str = "string",
        description: str = "",
        options: Optional[List] = None,
    ) -> None:
        """Add new configuration parameter."""
        self._config_data[key] = value
        logger.debug(f"Config added: {key} = {value} (type: {type})")

    async def remove(self, key: str) -> None:
        """Remove configuration parameter."""
        if key in self._config_data:
            del self._config_data[key]
            logger.debug(f"Config removed: {key}")


class MockCBPiActor:
    """Mock CraftBeerPi4 actor system."""

    def __init__(self):
        self._actors = {}
        self._actor_states = {}

    async def get_state(self, actor_id: str) -> bool:
        """Get actor state (on/off)."""
        if actor_id not in self._actor_states:
            raise KeyError(f"Actor '{actor_id}' not found")
        return self._actor_states.get(actor_id, False)

    async def set_state(self, actor_id: str, state: bool) -> None:
        """Set actor state."""
        self._actor_states[actor_id] = state
        logger.debug(f"Actor {actor_id} state set to {state}")

    async def on(self, actor_id: str, power: Optional[int] = None) -> None:
        """Turn actor on."""
        self._actor_states[actor_id] = True
        logger.debug(f"Actor {actor_id} turned on (power: {power})")

    async def off(self, actor_id: str) -> None:
        """Turn actor off."""
        self._actor_states[actor_id] = False
        logger.debug(f"Actor {actor_id} turned off")

    async def power(self, actor_id: str, power: int) -> None:
        """Set actor power level."""
        logger.debug(f"Actor {actor_id} power set to {power}%")

    async def get_actor(self, actor_id: str) -> Optional[Dict]:
        """Get actor configuration."""
        return self._actors.get(actor_id)

    def register_actor(self, actor_id: str, actor_config: Dict) -> None:
        """Register an actor for testing."""
        self._actors[actor_id] = actor_config
        self._actor_states[actor_id] = False


class MockCBPiSensor:
    """Mock CraftBeerPi4 sensor system."""

    def __init__(self):
        self._sensors = {}
        self._sensor_values = {}

    async def get_value(self, sensor_id: str) -> float:
        """Get sensor value."""
        return self._sensor_values.get(sensor_id, 0.0)

    async def set_value(self, sensor_id: str, value: float) -> None:
        """Set sensor value (for testing)."""
        self._sensor_values[sensor_id] = value
        logger.debug(f"Sensor {sensor_id} value set to {value}")

    async def get_sensor(self, sensor_id: str) -> Optional[Dict]:
        """Get sensor configuration."""
        return self._sensors.get(sensor_id)

    def register_sensor(self, sensor_id: str, sensor_config: Dict) -> None:
        """Register a sensor for testing."""
        self._sensors[sensor_id] = sensor_config
        self._sensor_values[sensor_id] = 20.0  # Default room temperature


class MockCBPiStep:
    """Mock CraftBeerPi4 step system."""

    def __init__(self):
        self._current_step = None
        self._step_queue = []

    async def get_current_step(self) -> Optional[Dict]:
        """Get current brewing step."""
        return self._current_step

    async def next(self) -> None:
        """Move to next step."""
        if self._step_queue:
            self._current_step = self._step_queue.pop(0)
            logger.debug(f"Moved to next step: {self._current_step}")

    async def previous(self) -> None:
        """Move to previous step."""
        logger.debug("Moved to previous step")

    async def reset(self) -> None:
        """Reset step sequence."""
        self._current_step = None
        self._step_queue = []
        logger.debug("Step sequence reset")


class MockCBPiNotification:
    """Mock CraftBeerPi4 notification system."""

    def __init__(self):
        self._notifications = []

    async def notify(self, title: str, message: str, type: str = "info", timeout: int = 5000) -> None:
        """Send notification."""
        notification = {
            "title": title,
            "message": message,
            "type": type,
            "timeout": timeout,
            "timestamp": datetime.now(),
        }
        self._notifications.append(notification)
        logger.debug(f"Notification sent: {title} - {message}")

    def get_notifications(self) -> List[Dict]:
        """Get all notifications (for testing)."""
        return self._notifications.copy()

    def clear_notifications(self) -> None:
        """Clear all notifications (for testing)."""
        self._notifications.clear()


class MockCBPiWebSocket:
    """Mock CraftBeerPi4 WebSocket system."""

    def __init__(self):
        self._messages = []

    async def send(self, data: Dict) -> None:
        """Send WebSocket message."""
        self._messages.append({"data": data, "timestamp": datetime.now()})
        logger.debug(f"WebSocket message sent: {data}")

    def get_messages(self) -> List[Dict]:
        """Get all sent messages (for testing)."""
        return self._messages.copy()

    def clear_messages(self) -> None:
        """Clear all messages (for testing)."""
        self._messages.clear()


class MockCBPiRecipe:
    """Mock CraftBeerPi4 recipe system."""

    def __init__(self):
        self._current_recipe = None
        self._recipes = {}

    async def get_current_recipe(self) -> Optional[Dict]:
        """Get current recipe."""
        return self._current_recipe

    async def set_current_recipe(self, recipe_id: str) -> None:
        """Set current recipe."""
        if recipe_id in self._recipes:
            self._current_recipe = self._recipes[recipe_id]
            logger.debug(f"Current recipe set to: {recipe_id}")

    def register_recipe(self, recipe_id: str, recipe_data: Dict) -> None:
        """Register a recipe for testing."""
        self._recipes[recipe_id] = recipe_data


# =============================================================================
# Main CBPI Mock Class
# =============================================================================


class MockCBPi:
    """Complete mock of CraftBeerPi4 system."""

    def __init__(self):
        self.config = MockCBPiConfig()
        self.actor = MockCBPiActor()
        self.sensor = MockCBPiSensor()
        self.step = MockCBPiStep()
        self.notification = MockCBPiNotification()
        self.ws = MockCBPiWebSocket()
        self.recipe = MockCBPiRecipe()

        # Additional properties
        self.running = True
        self.debug = True
        self.version = "4.0.0-test"

        # Plugin management
        self._plugins = {}
        self._extensions = {}

    async def register_plugin(self, plugin_name: str, plugin_instance: Any) -> None:
        """Register a plugin instance."""
        self._plugins[plugin_name] = plugin_instance
        logger.debug(f"Plugin registered: {plugin_name}")

    async def register_extension(self, extension_name: str, extension_instance: Any) -> None:
        """Register an extension instance."""
        self._extensions[extension_name] = extension_instance
        logger.debug(f"Extension registered: {extension_name}")

    def get_plugin(self, plugin_name: str) -> Any:
        """Get registered plugin."""
        return self._plugins.get(plugin_name)

    def get_extension(self, extension_name: str) -> Any:
        """Get registered extension."""
        return self._extensions.get(extension_name)


# =============================================================================
# CBPI API Mock Classes
# =============================================================================


class MockCBPiActorBase:
    """Mock base class for CBPi actors."""

    def __init__(self, cbpi: MockCBPi, id: str, props: Dict):
        self.cbpi = cbpi
        self.id = id
        self.props = props
        self.power = 0
        self.state = False

    async def on_start(self):
        """Called when actor starts."""
        pass

    async def on_stop(self):
        """Called when actor stops."""
        pass

    async def on(self, power: Optional[int] = None):
        """Turn actor on."""
        self.state = True
        if power is not None:
            self.power = power

    async def off(self):
        """Turn actor off."""
        self.state = False
        self.power = 0

    async def set_power(self, power: int):
        """Set actor power."""
        self.power = power


class MockCBPiSensorBase:
    """Mock base class for CBPi sensors."""

    def __init__(self, cbpi: MockCBPi, id: str, props: Dict):
        self.cbpi = cbpi
        self.id = id
        self.props = props
        self.value = 0.0
        self._task = None

    async def on_start(self):
        """Called when sensor starts."""
        self._task = asyncio.create_task(self.run())

    async def on_stop(self):
        """Called when sensor stops."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def run(self):
        """Main sensor loop."""
        while True:
            await asyncio.sleep(1)
            # Sensor reading logic would go here

    async def get_value(self) -> float:
        """Get sensor value."""
        return self.value

    async def set_value(self, value: float):
        """Set sensor value (for testing)."""
        self.value = value


class MockCBPiExtensionBase:
    """Mock base class for CBPi extensions."""

    def __init__(self, cbpi: MockCBPi):
        self.cbpi = cbpi
        self._task = None

    async def on_start(self):
        """Called when extension starts."""
        self._task = asyncio.create_task(self.run())

    async def on_stop(self):
        """Called when extension stops."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def run(self):
        """Main extension loop."""
        while True:
            await asyncio.sleep(1)
            # Extension logic would go here


# =============================================================================
# Plugin Testing Utilities
# =============================================================================


class PluginTestHarness:
    """Test harness for testing CBPI plugins in isolation."""

    def __init__(self):
        self.cbpi = MockCBPi()
        self.plugins = {}

    async def load_plugin(self, plugin_class, plugin_id: str, props: Optional[Dict] = None) -> Any:
        """Load and initialize a plugin for testing."""
        props = props or {}

        # Add props to config so plugin can access them
        for key, value in props.items():
            self.cbpi.config._config_data[key] = value

        # Create plugin instance
        # Check for plugin type hint first
        if hasattr(plugin_class, "_plugin_type"):
            plugin_type = plugin_class._plugin_type
            if plugin_type == "Extension":
                plugin_instance = plugin_class(self.cbpi)
            else:  # Actor or Sensor
                plugin_instance = plugin_class(self.cbpi, plugin_id, props)
        elif hasattr(plugin_class, "__bases__"):
            # Determine plugin type based on base class
            base_names = [base.__name__ for base in plugin_class.__bases__]

            # Also check for classes that contain 'Extension' in their
            # name (for mock classes)
            has_extension_base = any("CBPiExtension" in name or "Extension" in name for name in base_names)

            if "CBPiActor" in base_names:
                plugin_instance = plugin_class(self.cbpi, plugin_id, props)
            elif "CBPiSensor" in base_names:
                plugin_instance = plugin_class(self.cbpi, plugin_id, props)
            elif "CBPiExtension" in base_names or has_extension_base:
                plugin_instance = plugin_class(self.cbpi)
            else:
                plugin_instance = plugin_class(self.cbpi, plugin_id, props)
        else:
            plugin_instance = plugin_class(self.cbpi, plugin_id, props)

        # Populate config with props for extensions
        if props:
            for key, value in props.items():
                self.cbpi.config.set(key, value)

        # Register plugin
        await self.cbpi.register_plugin(plugin_id, plugin_instance)
        self.plugins[plugin_id] = plugin_instance

        # Start plugin
        if hasattr(plugin_instance, "on_start"):
            await plugin_instance.on_start()

        return plugin_instance

    async def unload_plugin(self, plugin_id: str) -> None:
        """Unload a plugin."""
        if plugin_id in self.plugins:
            plugin_instance = self.plugins[plugin_id]

            # Stop plugin with timeout to prevent hanging
            if hasattr(plugin_instance, "on_stop"):
                try:
                    async with async_timeout.timeout(2.0):
                        await plugin_instance.on_stop()
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout stopping plugin {plugin_id}")

            # Cancel any background tasks
            if hasattr(plugin_instance, "_task") and plugin_instance._task:
                if not plugin_instance._task.done():
                    plugin_instance._task.cancel()
                    try:
                        await plugin_instance._task
                    except asyncio.CancelledError:
                        pass

            # Remove from registry
            del self.plugins[plugin_id]
            if plugin_id in self.cbpi._plugins:
                del self.cbpi._plugins[plugin_id]

    async def cleanup(self) -> None:
        """Clean up all loaded plugins and cancel all pending tasks."""
        # First, unload all plugins
        plugin_ids = list(self.plugins.keys())
        for plugin_id in plugin_ids:
            await self.unload_plugin(plugin_id)

        # Cancel any remaining tasks
        current_task = asyncio.current_task()
        all_tasks = [task for task in asyncio.all_tasks() if task != current_task and not task.done()]

        if all_tasks:
            logger.debug(f"Cancelling {len(all_tasks)} remaining tasks")
            for task in all_tasks:
                task.cancel()

            # Wait for tasks to complete cancellation with timeout
            try:
                async with async_timeout.timeout(3.0):
                    await asyncio.gather(*all_tasks, return_exceptions=True)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for task cancellation")

        # Clear any remaining state
        self.plugins.clear()
        self.cbpi._plugins.clear()
        if hasattr(self.cbpi, "_extensions"):
            self.cbpi._extensions.clear()


# =============================================================================
# Mock Decorators and Utilities
# =============================================================================


def mock_cbpi_parameters(params: List[Dict]):
    """Mock the @parameters decorator."""

    def decorator(cls):
        cls._cbpi_parameters = params
        return cls

    return decorator


def create_mock_property(name: str, type_class: str, **kwargs):
    """Create a mock CBPi property."""
    return {
        "name": name,
        "type": type_class,
        "configurable": kwargs.get("configurable", True),
        "default_value": kwargs.get("default_value"),
        "options": kwargs.get("options", []),
        "description": kwargs.get("description", ""),
    }


# Mock the property types
class MockProperty:
    @staticmethod
    def Text(
        label: str,
        configurable: bool = True,
        default_value: str = "",
        description: str = "",
    ):
        return create_mock_property(
            label,
            "Text",
            configurable=configurable,
            default_value=default_value,
            description=description,
        )

    @staticmethod
    def Number(
        label: str,
        configurable: bool = True,
        default_value: float = 0.0,
        description: str = "",
    ):
        return create_mock_property(
            label,
            "Number",
            configurable=configurable,
            default_value=default_value,
            description=description,
        )

    @staticmethod
    def Select(label: str, options: List, configurable: bool = True, description: str = ""):
        return create_mock_property(
            label,
            "Select",
            configurable=configurable,
            options=options,
            description=description,
        )

    @staticmethod
    def Actor(label: str, configurable: bool = True, description: str = ""):
        return create_mock_property(label, "Actor", configurable=configurable, description=description)

    @staticmethod
    def Sensor(label: str, configurable: bool = True, description: str = ""):
        return create_mock_property(label, "Sensor", configurable=configurable, description=description)


# =============================================================================
# Factory Functions
# =============================================================================


def create_mock_cbpi() -> MockCBPi:
    """Factory function to create a configured CBPI mock."""
    return MockCBPi()


def create_plugin_test_harness() -> PluginTestHarness:
    """Factory function to create a plugin test harness."""
    return PluginTestHarness()


async def create_async_mock_cbpi() -> MockCBPi:
    """Factory function to create an async CBPI mock."""
    cbpi = MockCBPi()
    # Perform any async initialization here
    return cbpi
