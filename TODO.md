# Brewmotron Cache Handler - TODO

This file tracks planned enhancements and future work for the brewmotron cache handler.

## Phase 5: Configuration & User Experience

### High Priority

- [ ] **Add TTL Configuration to CraftBeerPi4 UI**
  - Expose cache TTL settings in cbpi4 configuration screen
  - Allow users to customize TTL values per cache type:
    - Step cache TTL (default: 500ms)
    - Kettle cache TTL (default: 1000ms)
    - Sensor cache TTL (default: 500ms)
    - Actor cache TTL (default: 250ms)
    - Config cache TTL (default: 60000ms)
  - Persist settings in cbpi4 config
  - Provide recommended ranges and explanations
  - Add validation (e.g., min: 50ms, max: 300000ms)
  - Hot-reload TTL changes without cache handler restart

### Medium Priority

- [ ] **Manual Event Publishing Helpers**
  - Add convenience methods for plugins to publish events when they modify data
  - Example: `await cache.publish_step_changed(step_data)`
  - Document event publishing patterns in migration guide
  - Encourage plugins to publish events after mutations
  - **Note**: cbpi4 has NO native event system, so automation is not possible
  - **Approach**: Rely on TTL-based caching + manual event publishing

- [ ] **Cache Performance Metrics Dashboard**
  - Add cbpi4 UI page showing cache statistics:
    - Hit rate per cache type
    - API call reduction percentage
    - Cache freshness metrics
    - I2C queue depth and throughput
    - Event bus subscription counts
  - Real-time metrics updates
  - Historical trends (last hour/day)

### Low Priority

- [ ] **Cache Warming on Startup**
  - Pre-fetch all cache types when cbpi4 starts
  - Reduce first-access latency
  - Warm cache immediately after singleton initialization

- [ ] **Enhanced Event Bus Features**
  - Event filtering (subscribers can filter by data properties)
  - Event priority/ordering
  - Persistent event history to disk (optional)
  - Event replay for debugging

## Phase 6: Advanced Features

- [ ] **WebSocket Integration**
  - Push cache updates to web UI via WebSocket
  - Eliminate UI polling entirely
  - Real-time dashboard updates

- [ ] **Multi-Level Caching**
  - Add L2 cache for historical data
  - Store last N values for trending
  - Useful for sensor history charts

- [ ] **Cache Persistence** (Optional)
  - Store cache to disk on cbpi4 shutdown
  - Restore on startup for instant availability
  - Useful for config cache (rarely changes)
  - Make optional per cache type

## Phase 7: Plugin Migration

- [ ] **Migrate 7SegDisplay Plugin**
  - Replace direct cbpi4 API calls with cache handler
  - Implement event-driven updates
  - Remove polling loops
  - Use I2C coordinator

- [ ] **Migrate LCDisplay Plugin**
  - Replace direct cbpi4 API calls with cache handler
  - Implement event-driven updates
  - Remove polling loops
  - Use I2C coordinator

- [ ] **Migrate BMT-Key Plugin**
  - Replace direct cbpi4 API calls with cache handler
  - Implement event-driven updates
  - Remove polling loops

## Documentation & Guides

- [ ] **Plugin Migration Guide**
  - Step-by-step instructions for migrating plugins to cache handler
  - Before/after code examples
  - Common pitfalls and solutions
  - Performance benchmarking template

- [ ] **Cache Handler API Reference**
  - Complete API documentation
  - Method signatures and parameters
  - Usage examples for each method
  - Best practices

- [ ] **Troubleshooting Guide**
  - Common issues and solutions
  - Debugging tips
  - Performance tuning recommendations
  - Cache statistics interpretation

## Testing

- [ ] **Hardware Integration Tests**
  - Test with real I2C devices (displays, sensors)
  - Verify bus coordination prevents conflicts
  - Measure actual performance improvements
  - Test under load (multiple displays updating)

- [ ] **Performance Benchmarks**
  - Baseline measurements without cache
  - With-cache measurements
  - API call reduction verification
  - Latency measurements
  - Memory usage profiling

---

## Completed

- [x] **Phase 1**: Core Cache Handler (cache_store.py, cache_entry.py)
- [x] **Phase 2**: Event Bus (event_bus.py)
- [x] **Phase 3**: I2C Coordinator (i2c_coordinator.py)
- [x] **Phase 4**: Main Cache Handler API (cache_handler.py)
- [x] **Phase 4.5**: Singleton Pattern (singleton.py)
- [x] **Documentation**: CBPI4_DATA_ACCESS_ARCHITECTURE.md
- [x] **Testing**: 209 tests with 96.87% coverage

---

## Event Bus Architecture - Current State

### What the Event Bus Provides (Already Implemented ✅)

The event bus is a **pub/sub infrastructure** for plugin-to-plugin communication:

```python
# Plugins can subscribe to events
await cache.subscribe_to_step_changes(callback)
await cache.subscribe_to_kettle_updates(callback)
await cache.subscribe_to_sensor_values(callback)

# Plugins can manually publish events
await cache._event_bus.publish(EventTopic.STEP_CHANGED, data)
```

### Current Use Cases

1. **Manual Event Publishing**: Plugins publish events when they KNOW data changed
   ```python
   # Plugin modifies step
   await cbpi.step.start_next()
   await cache.invalidate(CacheType.STEP)
   await cache._event_bus.publish(EventTopic.STEP_CHANGED, step_data)
   ```

2. **Plugin-to-Plugin Communication**: Instant notifications between plugins
   ```python
   # BMT-Key publishes button press
   await cache._event_bus.publish(EventTopic.ACTOR_STATE, actor_data)

   # 7SegDisplay receives notification instantly
   async def on_actor_changed(event):
       await update_display(event.data)
   ```

3. **TTL-Based Caching**: Default approach for most use cases
   - Cache automatically expires based on TTL (250ms-60s)
   - Plugins call `cache.get_X_state()` which fetches only if TTL expired
   - **94% reduction** in API calls (327 → <20 calls/min)
   - Acceptable staleness for brewing (500ms-1s)

### What the Event Bus Does NOT Do ❌

- **No automatic event publishing**: Nothing watches cbpi4 for changes
- **No cbpi4 integration**: cbpi4 has no native event system to hook into
- **No background monitoring**: No polling loop detecting changes (would increase API calls)

### Recommended Approach

1. **Primary**: Use TTL-based caching (current implementation)
   - Lazy/reactive: only fetches when plugins request data
   - Shared cache: multiple plugins benefit from single fetch
   - Bounded staleness: 500ms-1s is acceptable for brewing

2. **Secondary**: Manual event publishing when plugins modify data
   - Plugin invalidates cache after mutation
   - Plugin publishes event to notify other plugins
   - Other plugins receive instant updates via subscriptions

3. **Future**: If cbpi4 adds native events, integrate with them
   - Currently not possible (cbpi4 has no event system)
   - Would enable automatic cache invalidation
   - Deferred until cbpi4 provides this capability

---

**Last Updated**: 2025-11-16
**Maintained By**: MrLaister
