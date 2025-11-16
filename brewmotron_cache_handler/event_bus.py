"""
Event Bus for CraftBeerPi4 cache handler.

Provides a topic-based pub/sub system for notifying subscribers of data changes,
reducing the need for polling and enabling reactive plugin behavior.
"""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventTopic(str, Enum):
    """Event topics for CraftBeerPi4 data changes."""

    STEP_CHANGED = "step_changed"
    KETTLE_UPDATED = "kettle_updated"
    SENSOR_VALUE = "sensor_value"
    ACTOR_STATE = "actor_state"
    CONFIG_UPDATED = "config_updated"


@dataclass
class Event:
    """Represents an event published to the event bus."""

    topic: EventTopic
    data: Any
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    def to_dict(self) -> dict:
        """Convert event to dictionary representation."""
        return {
            "topic": self.topic.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventBus:
    """
    Async event bus with topic-based subscriptions.

    Provides pub/sub functionality for notifying plugins of data changes
    without requiring polling. Subscribers are called asynchronously and
    errors in one subscriber don't affect others.
    """

    def __init__(self, history_size: int = 100):
        """
        Initialize the event bus.

        Args:
            history_size: Number of events to retain per topic (default: 100)
        """
        self._subscribers: Dict[EventTopic, List[Callable]] = defaultdict(list)
        self._event_history: Dict[EventTopic, Deque[Event]] = defaultdict(lambda: deque(maxlen=history_size))
        self._history_size = history_size
        self._lock = asyncio.Lock()
        self._stats = {
            "events_published": 0,
            "events_delivered": 0,
            "delivery_errors": 0,
        }

    async def subscribe(self, topic: EventTopic, callback: Callable[[Event], Any]) -> None:
        """
        Subscribe to events on a specific topic.

        Args:
            topic: The event topic to subscribe to
            callback: Async function to call when events are published.
                     Signature: async def callback(event: Event) -> None
        """
        async with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
                logger.debug(f"Subscribed callback {callback.__name__} to topic {topic.value}")

    async def unsubscribe(self, topic: EventTopic, callback: Callable[[Event], Any]) -> bool:
        """
        Unsubscribe from events on a specific topic.

        Args:
            topic: The event topic to unsubscribe from
            callback: The callback function to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        async with self._lock:
            if callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)
                logger.debug(f"Unsubscribed callback {callback.__name__} from topic {topic.value}")
                return True
            return False

    async def publish(self, topic: EventTopic, data: Any) -> None:
        """
        Publish an event to all subscribers of a topic.

        Events are delivered asynchronously to all subscribers. If a subscriber
        raises an exception, it's logged but doesn't affect other subscribers.

        This method returns immediately without waiting for delivery to complete.

        Args:
            topic: The event topic to publish to
            data: The event data to send to subscribers
        """
        event = Event(topic=topic, data=data)

        # Add to history
        async with self._lock:
            self._event_history[topic].append(event)
            self._stats["events_published"] += 1
            subscribers = list(self._subscribers[topic])  # Copy to avoid lock contention

        # Deliver to subscribers asynchronously (fire-and-forget, outside lock)
        if subscribers:
            asyncio.create_task(self._deliver_event(event, subscribers))

    async def _deliver_event(self, event: Event, subscribers: List[Callable]) -> None:
        """
        Deliver an event to all subscribers.

        Each subscriber is called asynchronously. Errors are caught and logged
        individually to prevent one failing subscriber from affecting others.

        Args:
            event: The event to deliver
            subscribers: List of subscriber callbacks
        """
        tasks = []
        for callback in subscribers:
            tasks.append(self._safe_callback(callback, event))

        # Wait for all deliveries to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_callback(self, callback: Callable, event: Event) -> None:
        """
        Call a subscriber callback with error handling.

        Args:
            callback: The subscriber callback to call
            event: The event to pass to the callback
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
            self._stats["events_delivered"] += 1
        except Exception as e:
            self._stats["delivery_errors"] += 1
            logger.error(
                f"Error delivering event {event.topic.value} to {callback.__name__}: {e}",
                exc_info=True,
            )

    async def clear_subscribers(self, topic: Optional[EventTopic] = None) -> None:
        """
        Clear subscribers from one or all topics.

        Args:
            topic: Specific topic to clear, or None to clear all topics
        """
        async with self._lock:
            if topic is None:
                self._subscribers.clear()
                logger.debug("Cleared all subscribers from all topics")
            else:
                self._subscribers[topic].clear()
                logger.debug(f"Cleared all subscribers from topic {topic.value}")

    def get_history(self, topic: EventTopic, limit: Optional[int] = None) -> List[Event]:
        """
        Get recent event history for a topic.

        Args:
            topic: The topic to get history for
            limit: Maximum number of events to return (default: all)

        Returns:
            List of recent events, most recent last
        """
        history = list(self._event_history[topic])
        if limit:
            history = history[-limit:]
        return history

    def get_latest_event(self, topic: EventTopic) -> Optional[Event]:
        """
        Get the most recent event for a topic.

        Args:
            topic: The topic to get the latest event for

        Returns:
            The most recent event, or None if no events
        """
        history = self._event_history[topic]
        return history[-1] if history else None

    def get_subscriber_count(self, topic: EventTopic) -> int:
        """
        Get the number of subscribers for a topic.

        Args:
            topic: The topic to count subscribers for

        Returns:
            Number of subscribers
        """
        return len(self._subscribers[topic])

    def get_statistics(self) -> dict:
        """
        Get event bus statistics.

        Returns:
            Dictionary with statistics (events_published, events_delivered, delivery_errors)
        """
        return {
            **self._stats,
            "topics": {
                topic.value: {
                    "subscribers": len(self._subscribers[topic]),
                    "history_size": len(self._event_history[topic]),
                }
                for topic in EventTopic
            },
        }

    def reset_statistics(self) -> None:
        """Reset event bus statistics counters."""
        self._stats = {
            "events_published": 0,
            "events_delivered": 0,
            "delivery_errors": 0,
        }

    def __repr__(self) -> str:
        """Return string representation of EventBus."""
        total_subscribers = sum(len(subs) for subs in self._subscribers.values())
        return f"EventBus(subscribers={total_subscribers}, published={self._stats['events_published']})"
