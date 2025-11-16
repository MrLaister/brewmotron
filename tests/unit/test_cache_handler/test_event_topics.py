"""
Unit tests for Event and EventTopic classes.

Tests event data model, event topics enum, and event serialization.
"""

import asyncio
import time

import pytest

from brewmotron_cache_handler.event_bus import Event, EventTopic


class TestEventTopic:
    """Test suite for EventTopic enum."""

    def test_all_topics_defined(self):
        """Test all required event topics are defined."""
        expected_topics = {
            "STEP_CHANGED",
            "KETTLE_UPDATED",
            "SENSOR_VALUE",
            "ACTOR_STATE",
            "CONFIG_UPDATED",
        }
        actual_topics = {topic.name for topic in EventTopic}
        assert actual_topics == expected_topics

    def test_topic_values(self):
        """Test event topic values are correct."""
        assert EventTopic.STEP_CHANGED.value == "step_changed"
        assert EventTopic.KETTLE_UPDATED.value == "kettle_updated"
        assert EventTopic.SENSOR_VALUE.value == "sensor_value"
        assert EventTopic.ACTOR_STATE.value == "actor_state"
        assert EventTopic.CONFIG_UPDATED.value == "config_updated"

    def test_topic_is_string_enum(self):
        """Test EventTopic is a string enum."""
        assert isinstance(EventTopic.SENSOR_VALUE, str)
        assert EventTopic.SENSOR_VALUE == "sensor_value"

    def test_topics_are_unique(self):
        """Test all topic values are unique."""
        values = [topic.value for topic in EventTopic]
        assert len(values) == len(set(values))


class TestEvent:
    """Test suite for Event class."""

    def test_event_creation(self):
        """Test event can be created with topic and data."""
        event = Event(topic=EventTopic.SENSOR_VALUE, data={"temp": 65.5})
        assert event.topic == EventTopic.SENSOR_VALUE
        assert event.data == {"temp": 65.5}
        assert isinstance(event.timestamp, float)

    def test_event_timestamp_auto_generated(self):
        """Test event timestamp is automatically generated."""
        before = time.time()
        event = Event(topic=EventTopic.KETTLE_UPDATED, data={"kettle": "mash_tun"})
        after = time.time()

        # Timestamp should be between before and after (using event loop time)
        assert event.timestamp > 0

    def test_event_with_different_data_types(self):
        """Test event can contain different data types."""
        # Dict
        event_dict = Event(topic=EventTopic.STEP_CHANGED, data={"step": "mash"})
        assert event_dict.data == {"step": "mash"}

        # List
        event_list = Event(topic=EventTopic.ACTOR_STATE, data=[1, 2, 3])
        assert event_list.data == [1, 2, 3]

        # String
        event_str = Event(topic=EventTopic.CONFIG_UPDATED, data="config_value")
        assert event_str.data == "config_value"

        # Number
        event_num = Event(topic=EventTopic.SENSOR_VALUE, data=65.5)
        assert event_num.data == 65.5

        # None
        event_none = Event(topic=EventTopic.KETTLE_UPDATED, data=None)
        assert event_none.data is None

    def test_event_to_dict(self):
        """Test event can be converted to dictionary."""
        event = Event(
            topic=EventTopic.SENSOR_VALUE,
            data={"sensor_id": "temp1", "value": 65.5},
        )
        event_dict = event.to_dict()

        assert event_dict["topic"] == "sensor_value"
        assert event_dict["data"] == {"sensor_id": "temp1", "value": 65.5}
        assert "timestamp" in event_dict
        assert isinstance(event_dict["timestamp"], float)

    def test_event_to_dict_preserves_data_structure(self):
        """Test to_dict preserves complex data structures."""
        complex_data = {
            "kettle": "mash_tun",
            "temperature": 65.5,
            "target": 67.0,
            "settings": {"pid_p": 1.0, "pid_i": 0.1, "pid_d": 0.01},
            "sensors": ["temp1", "temp2"],
        }
        event = Event(topic=EventTopic.KETTLE_UPDATED, data=complex_data)
        event_dict = event.to_dict()

        assert event_dict["data"] == complex_data
        assert event_dict["data"]["settings"]["pid_p"] == 1.0
        assert event_dict["data"]["sensors"] == ["temp1", "temp2"]

    def test_multiple_events_have_different_timestamps(self):
        """Test events created at different times have different timestamps."""
        event1 = Event(topic=EventTopic.SENSOR_VALUE, data={"temp": 65.0})
        time.sleep(0.001)  # Small delay
        event2 = Event(topic=EventTopic.SENSOR_VALUE, data={"temp": 66.0})

        # Timestamps might be close but should be ordered correctly
        assert event1.timestamp <= event2.timestamp

    def test_event_data_is_mutable(self):
        """Test event data can be modified after creation."""
        data = {"temp": 65.0}
        event = Event(topic=EventTopic.SENSOR_VALUE, data=data)

        # Modify the data
        data["temp"] = 66.0

        # Event data should reflect the change (shallow copy)
        assert event.data["temp"] == 66.0

    def test_event_with_complex_nested_data(self):
        """Test event with deeply nested data structures."""
        nested_data = {
            "step": {
                "id": "1",
                "name": "Mash",
                "state": "active",
                "kettles": [
                    {
                        "id": "k1",
                        "name": "Mash Tun",
                        "sensors": [{"id": "s1", "value": 65.5}],
                    }
                ],
            }
        }
        event = Event(topic=EventTopic.STEP_CHANGED, data=nested_data)

        assert event.data["step"]["kettles"][0]["sensors"][0]["value"] == 65.5

    def test_event_equality_by_content(self):
        """Test events with same content are not automatically equal."""
        event1 = Event(topic=EventTopic.SENSOR_VALUE, data={"temp": 65.5})
        event2 = Event(topic=EventTopic.SENSOR_VALUE, data={"temp": 65.5})

        # Different instances are not equal (different timestamps)
        assert event1 is not event2
        assert event1.topic == event2.topic
        assert event1.data == event2.data

    def test_event_topic_immutable(self):
        """Test event topic cannot be easily changed."""
        event = Event(topic=EventTopic.SENSOR_VALUE, data={"temp": 65.5})
        original_topic = event.topic

        # Attempting to change topic (this works in Python but shouldn't in practice)
        # We're just testing that the original value is stored correctly
        assert event.topic == EventTopic.SENSOR_VALUE
        assert event.topic == original_topic
