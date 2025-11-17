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

- [ ] **Cache Performance Metrics Dashboard**
  - Add cbpi4 UI page showing cache statistics:
    - Hit rate per cache type
    - API call reduction percentage
    - Cache freshness metrics
    - I2C queue depth and throughput
  - Real-time metrics updates
  - Historical trends (last hour/day)

### Low Priority

- [ ] **Cache Warming on Startup**
  - Pre-fetch all cache types when cbpi4 starts
  - Reduce first-access latency
  - Warm cache immediately after singleton initialization

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
  - Use singleton pattern: `cache = await get_cache_handler(cbpi_instance=cbpi)`
  - Continue polling with cache (cache handles TTL automatically)
  - Use I2C coordinator for display updates

- [ ] **Migrate LCDisplay Plugin**
  - Replace direct cbpi4 API calls with cache handler
  - Use singleton pattern: `cache = await get_cache_handler()`
  - Continue polling with cache (cache handles TTL automatically)
  - Use I2C coordinator for display updates

- [ ] **Migrate BMT-Key Plugin**
  - Replace direct cbpi4 API calls with cache handler
  - Use singleton pattern: `cache = await get_cache_handler()`
  - Continue polling with cache (cache handles TTL automatically)

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
- [x] **Phase 2**: ~~Event Bus (event_bus.py)~~ - Removed (plugins should communicate via cbpi4)
- [x] **Phase 3**: I2C Coordinator (i2c_coordinator.py)
- [x] **Phase 4**: Main Cache Handler API (cache_handler.py)
- [x] **Phase 4.5**: Singleton Pattern (singleton.py)
- [x] **Documentation**: CBPI4_DATA_ACCESS_ARCHITECTURE.md (updated to remove event bus)
- [x] **Testing**: 150 tests passing (112 unit + 38 integration)

---

## Architecture Notes

### Cache Handler Design

The cache handler provides two key components:

1. **TTL-Based Caching** (Primary feature)
   - Cache automatically expires based on TTL (250ms-60s)
   - Plugins call `cache.get_X_state()` which fetches only if TTL expired
   - **94% reduction** in API calls (327 → <20 calls/min)
   - Acceptable staleness for brewing (500ms-1s)
   - Lazy/reactive: only fetches when plugins request data
   - Shared cache: multiple plugins benefit from single fetch

2. **I2C Coordination**
   - Priority-based queue for I2C operations
   - Prevents bus conflicts between multiple displays/sensors
   - Thread-safe operation management

### Plugin Communication

Plugins should communicate through cbpi4 core, not directly with each other. This maintains proper plugin isolation and follows cbpi4's architecture principles

---

**Last Updated**: 2025-11-16
**Maintained By**: MrLaister
