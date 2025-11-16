"""
Unit tests for event delivery mechanisms.

Tests async event delivery, error handling, concurrent access,
and delivery guarantees.
"""

import asyncio

import pytest

from brewmotron_cache_handler.event_bus import Event, EventBus, EventTopic


class TestEventDelivery:
    """Test suite for event delivery mechanisms."""

    @pytest.mark.asyncio
    async def test_async_callback_delivery(self):
        """Test async callbacks are properly awaited."""
        bus = EventBus()
        received = []

        async def async_callback(event: Event):
            await asyncio.sleep(0.01)  # Simulate async work
            received.append(event.data)

        await bus.subscribe(EventTopic.SENSOR_VALUE, async_callback)
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})

        # Wait for delivery
        await asyncio.sleep(0.02)

        assert len(received) == 1
        assert received[0] == {"temp": 65.5}

    @pytest.mark.asyncio
    async def test_sync_callback_delivery(self):
        """Test synchronous callbacks work correctly."""
        bus = EventBus()
        received = []

        def sync_callback(event: Event):
            received.append(event.data)

        await bus.subscribe(EventTopic.KETTLE_UPDATED, sync_callback)
        await bus.publish(EventTopic.KETTLE_UPDATED, {"kettle": "mash_tun"})

        await asyncio.sleep(0.01)

        assert len(received) == 1
        assert received[0] == {"kettle": "mash_tun"}

    @pytest.mark.asyncio
    async def test_failed_subscriber_doesnt_block_others(self):
        """Test error in one subscriber doesn't prevent others from receiving events."""
        bus = EventBus()
        successful_calls = []

        async def failing_callback(event: Event):
            raise RuntimeError("Callback error")

        async def success_callback1(event: Event):
            successful_calls.append(1)

        async def success_callback2(event: Event):
            successful_calls.append(2)

        await bus.subscribe(EventTopic.STEP_CHANGED, success_callback1)
        await bus.subscribe(EventTopic.STEP_CHANGED, failing_callback)
        await bus.subscribe(EventTopic.STEP_CHANGED, success_callback2)

        await bus.publish(EventTopic.STEP_CHANGED, {"step": "mash"})

        await asyncio.sleep(0.01)

        # Both successful callbacks should have been called
        assert len(successful_calls) == 2
        assert 1 in successful_calls
        assert 2 in successful_calls

        # Error should be tracked in statistics
        stats = bus.get_statistics()
        assert stats["delivery_errors"] == 1
        assert stats["events_delivered"] == 2

    @pytest.mark.asyncio
    async def test_multiple_errors_tracked(self):
        """Test multiple subscriber errors are tracked correctly."""
        bus = EventBus()

        async def failing_callback1(event: Event):
            raise ValueError("Error 1")

        async def failing_callback2(event: Event):
            raise KeyError("Error 2")

        await bus.subscribe(EventTopic.ACTOR_STATE, failing_callback1)
        await bus.subscribe(EventTopic.ACTOR_STATE, failing_callback2)

        await bus.publish(EventTopic.ACTOR_STATE, {"actor": "pump"})

        await asyncio.sleep(0.01)

        stats = bus.get_statistics()
        assert stats["delivery_errors"] == 2
        assert stats["events_delivered"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_event_publishing(self):
        """Test multiple events can be published concurrently."""
        bus = EventBus()
        received = []

        async def callback(event: Event):
            await asyncio.sleep(0.01)
            received.append(event.data)

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)

        # Publish multiple events concurrently
        await asyncio.gather(
            bus.publish(EventTopic.SENSOR_VALUE, {"id": 1}),
            bus.publish(EventTopic.SENSOR_VALUE, {"id": 2}),
            bus.publish(EventTopic.SENSOR_VALUE, {"id": 3}),
        )

        await asyncio.sleep(0.02)

        # All events should be delivered
        assert len(received) == 3
        ids = [item["id"] for item in received]
        assert set(ids) == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_delivery_order_preserved(self):
        """Test events are delivered in published order."""
        bus = EventBus()
        received = []

        async def callback(event: Event):
            received.append(event.data)

        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback)

        # Publish events sequentially
        for i in range(5):
            await bus.publish(EventTopic.KETTLE_UPDATED, {"count": i})

        await asyncio.sleep(0.01)

        # Events should be received in order
        assert len(received) == 5
        for i, data in enumerate(received):
            assert data["count"] == i

    @pytest.mark.asyncio
    async def test_async_delivery_doesnt_block_publisher(self):
        """Test publish returns quickly even with slow subscribers."""
        bus = EventBus()

        async def slow_callback(event: Event):
            await asyncio.sleep(0.1)  # 100ms delay

        await bus.subscribe(EventTopic.STEP_CHANGED, slow_callback)

        # Publish should return quickly
        start = asyncio.get_event_loop().time()
        await bus.publish(EventTopic.STEP_CHANGED, {"step": "mash"})
        elapsed = asyncio.get_event_loop().time() - start

        # Publish should not wait for slow callback
        assert elapsed < 0.05  # Should be much faster than 100ms

    @pytest.mark.asyncio
    async def test_subscriber_receives_correct_event_data(self):
        """Test subscriber receives exact event data published."""
        bus = EventBus()
        received_event = None

        async def callback(event: Event):
            nonlocal received_event
            received_event = event

        await bus.subscribe(EventTopic.CONFIG_UPDATED, callback)

        complex_data = {
            "section": "system",
            "key": "brewery_name",
            "value": "Test Brewery",
            "metadata": {"user": "admin", "timestamp": 123456789},
        }

        await bus.publish(EventTopic.CONFIG_UPDATED, complex_data)
        await asyncio.sleep(0.01)

        assert received_event is not None
        assert received_event.topic == EventTopic.CONFIG_UPDATED
        assert received_event.data == complex_data
        assert received_event.data["metadata"]["user"] == "admin"

    @pytest.mark.asyncio
    async def test_unsubscribe_during_delivery(self):
        """Test unsubscribing during event delivery."""
        bus = EventBus()
        call_count = 0

        async def callback(event: Event):
            nonlocal call_count
            call_count += 1

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})

        await asyncio.sleep(0.01)
        assert call_count == 1

        # Unsubscribe
        await bus.unsubscribe(EventTopic.SENSOR_VALUE, callback)

        # Publish again - should not be delivered
        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 66.0})
        await asyncio.sleep(0.01)

        # Call count should not increase
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_topics_independent_delivery(self):
        """Test events on different topics are delivered independently."""
        bus = EventBus()
        sensor_calls = []
        kettle_calls = []

        async def sensor_callback(event: Event):
            sensor_calls.append(event.data)

        async def kettle_callback(event: Event):
            kettle_calls.append(event.data)

        await bus.subscribe(EventTopic.SENSOR_VALUE, sensor_callback)
        await bus.subscribe(EventTopic.KETTLE_UPDATED, kettle_callback)

        await bus.publish(EventTopic.SENSOR_VALUE, {"temp": 65.5})
        await bus.publish(EventTopic.KETTLE_UPDATED, {"kettle": "mash_tun"})

        await asyncio.sleep(0.01)

        assert len(sensor_calls) == 1
        assert len(kettle_calls) == 1
        assert sensor_calls[0] == {"temp": 65.5}
        assert kettle_calls[0] == {"kettle": "mash_tun"}

    @pytest.mark.asyncio
    async def test_callback_exception_details_logged(self):
        """Test callback exceptions include proper context."""
        bus = EventBus()

        async def callback_with_name_error(event: Event):
            # This will raise NameError
            nonexistent_variable  # noqa: F821

        await bus.subscribe(EventTopic.ACTOR_STATE, callback_with_name_error)
        await bus.publish(EventTopic.ACTOR_STATE, {"actor": "pump"})

        await asyncio.sleep(0.01)

        stats = bus.get_statistics()
        assert stats["delivery_errors"] == 1

    @pytest.mark.asyncio
    async def test_high_volume_event_delivery(self):
        """Test event bus handles high volume of events."""
        bus = EventBus()
        received = []

        async def callback(event: Event):
            received.append(event.data["count"])

        await bus.subscribe(EventTopic.SENSOR_VALUE, callback)

        # Publish 100 events
        for i in range(100):
            await bus.publish(EventTopic.SENSOR_VALUE, {"count": i})

        await asyncio.sleep(0.1)

        # All events should be delivered
        assert len(received) == 100
        assert set(received) == set(range(100))

    @pytest.mark.asyncio
    async def test_concurrent_subscribe_and_publish(self):
        """Test subscribing and publishing can happen concurrently."""
        bus = EventBus()
        received = []

        async def callback(event: Event):
            received.append(event.data)

        async def subscribe_task():
            await bus.subscribe(EventTopic.STEP_CHANGED, callback)

        async def publish_task():
            await asyncio.sleep(0.001)  # Small delay
            await bus.publish(EventTopic.STEP_CHANGED, {"step": "mash"})

        # Run subscribe and publish concurrently
        await asyncio.gather(subscribe_task(), publish_task())
        await asyncio.sleep(0.01)

        # Event should be delivered if subscribe completed first
        # Or not delivered if publish completed first
        # Both outcomes are valid for concurrent operations
        assert len(received) <= 1

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_unsubscribe(self):
        """Test memory is properly cleaned up after unsubscribe."""
        bus = EventBus()

        async def callback(event: Event):
            pass

        # Subscribe and unsubscribe multiple times
        for _ in range(10):
            await bus.subscribe(EventTopic.SENSOR_VALUE, callback)
            await bus.unsubscribe(EventTopic.SENSOR_VALUE, callback)

        # Should end with no subscribers
        assert bus.get_subscriber_count(EventTopic.SENSOR_VALUE) == 0

    @pytest.mark.asyncio
    async def test_callback_receives_event_object(self):
        """Test callback receives proper Event object, not just data."""
        bus = EventBus()
        received_event = None

        async def callback(event: Event):
            nonlocal received_event
            received_event = event

        await bus.subscribe(EventTopic.KETTLE_UPDATED, callback)
        await bus.publish(EventTopic.KETTLE_UPDATED, {"kettle": "mash_tun"})

        await asyncio.sleep(0.01)

        assert received_event is not None
        assert isinstance(received_event, Event)
        assert hasattr(received_event, "topic")
        assert hasattr(received_event, "data")
        assert hasattr(received_event, "timestamp")
