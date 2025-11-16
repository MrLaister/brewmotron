"""
Unit tests for EventBus class.

Tests basic event bus functionality including subscription management,
event publishing, history tracking, and statistics.
"""

import asyncio

import pytest

from brewmotron_cache_handler.event_bus import Event, EventBus, EventTopic


class TestEventBus:
    """Test suite for EventBus class."""

    @pytest.mark.asyncio
    async def test_event_bus_initialization(self):
        """Test event bus can be created with default settings."""
        bus = EventBus()
        assert bus is not None
        assert bus._history_size == 100
        stats = bus.get_statistics()
        assert stats["events_published"] == 0
        assert stats["events_delivered"] == 0

    @pytest.mark.asyncio
    async def test_event_bus_custom_history_size(self):
        """Test event bus can be created with custom history size."""
        bus = EventBus(history_size=50)
        assert bus._history_size == 50

    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self):
        """Test subscribing a callback to a topic."""
        bus = EventBus()
        called = False

        async def callback(event: Event):
            nonlocal called
            called = True

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
        assert bus.get_subscriber_count(EventTopic.SENSOR_VALUE) == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_topic(self):
        """Test multiple subscribers can subscribe to same topic."""
        bus = EventBus()

        async def callback1(event: Event):
            pass

        async def callback2(event: Event):
            pass

        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback1)
        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback2)
        assert bus.get_subscriber_count(EventTopic.KETTLE_UPDATED) == 2

    @pytest.mark.asyncio
    async def test_duplicate_subscription_ignored(self):
        """Test subscribing same callback twice doesn't create duplicates."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        await bus.subscribe(EventTopic.STEP_CHANGED, callback)
        await bus.subscribe(EventTopic.STEP_CHANGED, callback)
        assert bus.get_subscriber_count(EventTopic.STEP_CHANGED) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic(self):
        """Test unsubscribing a callback from a topic."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        await bus.subscribe(EventTopic.ACTOR_STATE, callback)
        result = await bus.unsubscribe(EventTopic.ACTOR_STATE, callback)
        assert result is True
        assert bus.get_subscriber_count(EventTopic.ACTOR_STATE) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_callback(self):
        """Test unsubscribing a callback that wasn't subscribed returns False."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        result = await bus.unsubscribe(EventTopic.CONFIG_UPDATED, callback)
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_event_to_subscriber(self):
        """Test publishing an event delivers it to subscriber."""
        bus = EventBus()
        received_event = None

        async def callback(event: Event):
            nonlocal received_event
            received_event = event

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})

        # Give event delivery time to complete
        await asyncio.sleep(0.01)

        assert received_event is not None
        assert received_event.topic == EventTopic.SENSOR_VALUE
        assert received_event.data == {"temp": 65.5}

    @pytest.mark.asyncio
    async def test_publish_event_to_multiple_subscribers(self):
        """Test event is delivered to all subscribers."""
        bus = EventBus()
        call_count = 0

        async def callback1(event: Event):
            nonlocal call_count
            call_count += 1

        async def callback2(event: Event):
            nonlocal call_count
            call_count += 1

        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback1)
        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback2)
        await bus.publish(EventTopic.KETTLE_UPDATED, {"kettle": "mash_tun"})

        await asyncio.sleep(0.01)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_publish_to_topic_without_subscribers(self):
        """Test publishing to topic without subscribers doesn't error."""
        bus = EventBus()
        # Should not raise exception
        await bus.publish(EventTopic.STEP_CHANGED, {"step": "mash"})

    @pytest.mark.asyncio
    async def test_event_history_stored(self):
        """Test events are stored in history."""
        bus = EventBus()
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 66.0})

        history = bus.get_history(EventTopic.SENSOR_VALUE)
        assert len(history) == 2
        assert history[0].data == {"temp": 65.5}
        assert history[1].data == {"temp": 66.0}

    @pytest.mark.asyncio
    async def test_event_history_respects_limit(self):
        """Test event history respects size limit."""
        bus = EventBus(history_size=3)

        for i in range(5):
            await bus.publish(EventTopic.ACTOR_STATE, {"count": i})

        history = bus.get_history(EventTopic.ACTOR_STATE)
        # Only last 3 events should be retained
        assert len(history) == 3
        assert history[0].data == {"count": 2}
        assert history[1].data == {"count": 3}
        assert history[2].data == {"count": 4}

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self):
        """Test getting history with custom limit."""
        bus = EventBus()

        for i in range(5):
            await bus.publish(EventTopic.CONFIG_UPDATED, {"count": i})

        history = bus.get_history(EventTopic.CONFIG_UPDATED, limit=2)
        assert len(history) == 2
        # Should get last 2 events
        assert history[0].data == {"count": 3}
        assert history[1].data == {"count": 4}

    @pytest.mark.asyncio
    async def test_get_latest_event(self):
        """Test getting the most recent event."""
        bus = EventBus()
        await bus.publish(EventTopic.KETTLE_UPDATED, {"temp": 65.0})
        await bus.publish(EventTopic.KETTLE_UPDATED, {"temp": 66.0})

        latest = bus.get_latest_event(EventTopic.KETTLE_UPDATED)
        assert latest is not None
        assert latest.data == {"temp": 66.0}

    @pytest.mark.asyncio
    async def test_get_latest_event_when_empty(self):
        """Test getting latest event when no events published returns None."""
        bus = EventBus()
        latest = bus.get_latest_event(EventTopic.STEP_CHANGED)
        assert latest is None

    @pytest.mark.asyncio
    async def test_clear_subscribers_for_topic(self):
        """Test clearing subscribers for a specific topic."""
        bus = EventBus()

        async def callback1(event: Event):
            pass

        async def callback2(event: Event):
            pass

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback1)
        await bus.subscribe(EventTopic.ACTOR_STATE, callback2)

        await bus.clear_subscribers(EventTopic.SENSOR_VALUE)

        assert bus.get_subscriber_count(EventTopic.SENSOR_VALUE) == 0
        assert bus.get_subscriber_count(EventTopic.ACTOR_STATE) == 1

    @pytest.mark.asyncio
    async def test_clear_all_subscribers(self):
        """Test clearing all subscribers from all topics."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback)

        await bus.clear_subscribers()

        assert bus.get_subscriber_count(EventTopic.SENSOR_VALUE) == 0
        assert bus.get_subscriber_count(EventTopic.KETTLE_UPDATED) == 0

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Test event bus tracks statistics correctly."""
        bus = EventBus()
        call_count = 0

        async def callback(event: Event):
            nonlocal call_count
            call_count += 1

        await bus.subscribe(EventTopic.STEP_CHANGED, callback)
        await bus.publish(EventTopic.STEP_CHANGED, {"step": "mash"})

        await asyncio.sleep(0.01)

        stats = bus.get_statistics()
        assert stats["events_published"] == 1
        assert stats["events_delivered"] == 1
        assert stats["delivery_errors"] == 0

    @pytest.mark.asyncio
    async def test_reset_statistics(self):
        """Test statistics can be reset."""
        bus = EventBus()
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})

        bus.reset_statistics()

        stats = bus.get_statistics()
        assert stats["events_published"] == 0
        assert stats["events_delivered"] == 0
        assert stats["delivery_errors"] == 0

    @pytest.mark.asyncio
    async def test_repr_string(self):
        """Test string representation of EventBus."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})

        repr_str = repr(bus)
        assert "EventBus" in repr_str
        assert "subscribers=1" in repr_str
        assert "published=1" in repr_str

    @pytest.mark.asyncio
    async def test_subscriber_count_for_different_topics(self):
        """Test subscriber counts are independent per topic."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback)
        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback)  # Duplicate ignored

        assert bus.get_subscriber_count(EventTopic.SENSOR_VALUE) == 1
        assert bus.get_subscriber_count(EventTopic.KETTLE_UPDATED) == 1
        assert bus.get_subscriber_count(EventTopic.STEP_CHANGED) == 0
