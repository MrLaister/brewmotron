# Cache Handler Deployment Plan

## Strategy: Complete-Then-Merge

This document outlines the deployment strategy for implementing the CraftBeerPi4 Cache Handler architecture. We will build the complete solution on the feature branch `claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB`, test thoroughly in stages, then deploy to production (main branch) in a single merge event.

**Key Principle**: Main branch remains stable and production-ready throughout development. No partial implementations will be merged.

---

## Development Timeline

### Assumptions
- Main branch will not change during development (single-user, non-public)
- All development occurs on feature branch
- Testing uses existing test infrastructure + new cache handler tests
- Deployment to prod occurs only after complete validation

### Estimated Duration
- **Phase 1-3**: 2-3 weeks (core infrastructure)
- **Phase 4-5**: 2-3 weeks (plugin migration)
- **Phase 6**: 1 week (integration testing and validation)
- **Total**: 5-7 weeks

---

## Phase-by-Phase Implementation

### Phase 1: Core Cache Handler (Week 1-2)

#### Deliverables
- [x] Architecture documentation (CBPI4_DATA_ACCESS_ARCHITECTURE.md)
- [ ] `brewmotron_cache_handler/` package structure
- [ ] `cache_store.py` - TTL-based cache with automatic expiration
- [ ] `cache_entry.py` - Cache entry data model
- [ ] Unit tests for cache logic (>80% coverage)

#### Tasks
1. Create package structure:
   ```
   brewmotron_cache_handler/
   ├── __init__.py
   ├── cache_store.py      # TTL cache implementation
   ├── cache_entry.py      # Data model for cached entries
   └── README.md           # Package documentation
   ```

2. Implement `CacheEntry` class:
   - Data storage
   - Timestamp tracking
   - TTL validation
   - Expiration logic

3. Implement `DataCache` class:
   - Step cache (TTL: 500ms)
   - Kettle cache (TTL: 1000ms)
   - Sensor cache (TTL: 500ms)
   - Actor cache (TTL: 250ms)
   - Config cache (TTL: 60000ms)

4. Add cache operations:
   - `get(cache_type, force_refresh=False)`
   - `set(cache_type, data)`
   - `invalidate(cache_type)`
   - `is_valid(cache_type)`

5. Create comprehensive unit tests:
   ```
   tests/unit/test_cache_handler/
   ├── test_cache_entry.py
   ├── test_cache_store.py
   └── test_ttl_behavior.py
   ```

#### Testing Checklist
- [ ] Cache entries expire after TTL
- [ ] Cache returns fresh data when valid
- [ ] Cache fetches new data when expired
- [ ] Invalidation works correctly
- [ ] Force refresh bypasses cache
- [ ] Thread-safety (async-safe)
- [ ] Memory usage is reasonable
- [ ] All unit tests pass with >80% coverage

#### Completion Criteria
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Code review (self-review with documentation)
- [ ] Commit with descriptive message
- [ ] Push to feature branch

---

### Phase 2: Event Bus Implementation (Week 2-3)

#### Deliverables
- [ ] `event_bus.py` - Pub/sub event system
- [ ] Event topic definitions
- [ ] Unit tests for event bus (>80% coverage)

#### Tasks
1. Implement `EventBus` class:
   - Topic-based subscription system
   - Async event publishing
   - Subscriber management
   - Event queuing and delivery

2. Define event topics:
   - `step_changed` - Brewing step state changes
   - `kettle_updated` - Kettle temperature/target changes
   - `sensor_value` - Sensor reading updates
   - `actor_state` - Actor on/off/power changes
   - `config_updated` - Configuration changes

3. Implement subscription API:
   - `subscribe(topic, callback)`
   - `unsubscribe(topic, callback)`
   - `publish(topic, data)`
   - `clear_subscribers(topic=None)`

4. Add event delivery mechanisms:
   - Async callback execution
   - Error handling (failed subscribers don't block others)
   - Event history (last N events per topic)
   - Subscriber filtering/priorities

5. Create unit tests:
   ```
   tests/unit/test_cache_handler/
   ├── test_event_bus.py
   ├── test_event_topics.py
   └── test_event_delivery.py
   ```

#### Testing Checklist
- [ ] Subscribers receive published events
- [ ] Multiple subscribers work correctly
- [ ] Failed subscriber doesn't affect others
- [ ] Unsubscribe works correctly
- [ ] Events delivered in correct order
- [ ] Async delivery doesn't block publisher
- [ ] Memory leaks prevented (subscriber cleanup)
- [ ] All unit tests pass with >80% coverage

#### Completion Criteria
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Integration with cache store tested
- [ ] Commit and push to feature branch

---

### Phase 3: I2C Coordinator (Week 3-4)

#### Deliverables
- [ ] `i2c_coordinator.py` - Queued I2C bus access
- [ ] Priority queue implementation
- [ ] Deadlock detection and prevention
- [ ] Integration tests with hardware mocks

#### Tasks
1. Implement `I2CCoordinator` class:
   - Async queue for I2C operations
   - Priority-based scheduling
   - Mutex/lock for bus access
   - Retry logic for failed operations

2. Add I2C operations:
   - `enqueue_write(address, data, priority=5)`
   - `enqueue_read(address, register, priority=5)`
   - `process_queue()` (background task)
   - `flush_queue()`

3. Implement priority levels:
   - Critical: 1 (sensor reads during brewing)
   - Normal: 5 (display updates)
   - Low: 10 (configuration reads)

4. Add safety features:
   - Bus timeout detection
   - Deadlock prevention
   - Queue overflow protection
   - Operation retry with backoff

5. Create integration tests:
   ```
   tests/integration/test_cache_handler/
   ├── test_i2c_coordinator.py
   ├── test_i2c_priority.py
   └── test_i2c_contention.py
   ```

#### Testing Checklist
- [ ] Operations queued correctly
- [ ] Priority ordering respected
- [ ] Mutex prevents bus conflicts
- [ ] Failed operations retry correctly
- [ ] Queue overflow handled gracefully
- [ ] Background processor works continuously
- [ ] No deadlocks under high load
- [ ] Integration tests pass with mocks

#### Completion Criteria
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Hardware mock testing successful
- [ ] Performance benchmarked (throughput, latency)
- [ ] Commit and push to feature branch

---

### Phase 4: Main Cache Handler API (Week 4-5)

#### Deliverables
- [ ] `cache_handler.py` - Main API facade
- [ ] Backward-compatible wrapper
- [ ] Integration with CraftBeerPi4 core
- [ ] Comprehensive unit and integration tests

#### Tasks
1. Implement `CBPI4CacheHandler` class:
   - Integrates cache store, event bus, I2C coordinator
   - Provides unified API for plugins
   - Handles CraftBeerPi4 core interactions

2. Add async data access methods:
   - `async get_step_state() -> dict`
   - `async get_kettle_state() -> dict`
   - `async get_sensor_state() -> dict`
   - `async get_sensor_value(sensor_id) -> float`
   - `async get_actor_state() -> dict`

3. Add cache management methods:
   - `async invalidate(cache_type)`
   - `async refresh_all()`
   - `async warm_cache()`
   - `get_cache_stats()`

4. Add event subscription helpers:
   - `async subscribe_to_step_changes(callback)`
   - `async subscribe_to_kettle_updates(callback)`
   - `async subscribe_to_sensor_values(callback)`
   - `async subscribe_to_actor_state(callback)`

5. Add I2C coordination helpers:
   - `async i2c_write(address, data, priority=5)`
   - `async i2c_read(address, register, priority=5)`

6. Implement backward compatibility layer:
   ```python
   class CBPiCompat:
       """Provides old synchronous API using cache handler"""
       def get_state(self):
           return asyncio.run(self.cache.get_state())
   ```

7. Create comprehensive tests:
   ```
   tests/unit/test_cache_handler/
   ├── test_cache_handler_api.py
   ├── test_backward_compat.py
   └── test_cache_integration.py

   tests/integration/test_cache_handler/
   └── test_full_cache_handler.py
   ```

#### Testing Checklist
- [ ] All async methods work correctly
- [ ] Cache invalidation propagates
- [ ] Event subscriptions trigger callbacks
- [ ] I2C operations queued properly
- [ ] Backward compatibility layer works
- [ ] Cache warming on startup
- [ ] Statistics tracking accurate
- [ ] All unit tests pass (>80% coverage)
- [ ] Integration tests pass

#### Completion Criteria
- [ ] All tasks completed
- [ ] All tests passing
- [ ] API documentation complete
- [ ] Performance metrics collected
- [ ] Commit and push to feature branch

---

### Phase 5: Plugin Migration (Week 5-6)

#### Deliverables
- [ ] Updated 7SegDisplay plugin (proof of concept)
- [ ] Updated LCDisplay plugin
- [ ] Updated BMT-Key plugin
- [ ] Migration guide for plugin developers
- [ ] Integration tests for migrated plugins

#### Plugin Migration Order
1. **7SegDisplay** (most complex, proof of concept)
2. **LCDisplay** (similar pattern to 7Seg)
3. **BMT-Key** (simplest, validates actor access)

#### Tasks per Plugin

**For Each Plugin:**

1. Add cache handler import:
   ```python
   from brewmotron_cache_handler import CBPI4CacheHandler
   ```

2. Initialize in `__init__`:
   ```python
   def __init__(self, cbpi):
       self.cbpi = cbpi
       self.cache = CBPI4CacheHandler(cbpi)
   ```

3. Replace polling loop with event subscriptions:
   ```python
   # Old: while True polling
   # New: Event-driven callbacks
   await self.cache.subscribe_to_step_changes(self.on_step_changed)
   await self.cache.subscribe_to_kettle_updates(self.on_kettle_updated)
   ```

4. Replace synchronous get_state() calls:
   ```python
   # Old: step_data = self.cbpi.step.get_state()
   # New: step_data = await self.cache.get_step_state()
   ```

5. Replace direct I2C access with coordinator:
   ```python
   # Old: display.hardware.print(text)
   # New: await self.cache.i2c_write(address, formatted_data)
   ```

6. Create plugin-specific tests:
   ```
   tests/integration/test_plugins_with_cache/
   ├── test_7seg_with_cache.py
   ├── test_lcd_with_cache.py
   └── test_bmtkey_with_cache.py
   ```

#### Testing Checklist (Per Plugin)
- [ ] Plugin initializes with cache handler
- [ ] Event subscriptions work correctly
- [ ] Display updates on events (not polling)
- [ ] I2C operations coordinated
- [ ] No regression in functionality
- [ ] Performance improved (measure API calls)
- [ ] Plugin-specific tests pass
- [ ] Integration with other plugins works

#### 7SegDisplay Migration Checklist
- [ ] Replace main run() loop with event handlers
- [ ] Migrate get_active_step_values() to cache
- [ ] Migrate get_kettle_values() to cache
- [ ] Migrate get_sensor_values_by_id() to cache
- [ ] Migrate get_actor_gpio() to cache
- [ ] Replace I2C writes with coordinator
- [ ] Test display updates with real hardware (optional)

#### LCDisplay Migration Checklist
- [ ] Replace main run() loop with event handlers
- [ ] Migrate get_active_step_values() to cache
- [ ] Migrate get_kettle_values() to cache
- [ ] Migrate get_sensor_values_by_id() to cache
- [ ] Replace I2C writes with coordinator
- [ ] Test all display modes (multi/single/sensor)

#### BMT-Key Migration Checklist
- [ ] Replace check_state() polling with events
- [ ] Migrate loadActorValues() to cache
- [ ] Migrate actor state checks to cache
- [ ] Test mode switching functionality

#### Completion Criteria
- [ ] All three plugins migrated
- [ ] All plugin-specific tests passing
- [ ] Performance benchmarks show improvement
- [ ] Migration guide documented
- [ ] Commit and push to feature branch

---

### Phase 6: Integration Testing & Validation (Week 6-7)

#### Deliverables
- [ ] Full system integration tests
- [ ] Performance benchmarking results
- [ ] Pre-merge validation report
- [ ] Deployment documentation

#### Tasks

1. **Comprehensive Integration Testing**
   - [ ] Run all existing unit tests (128+ tests)
   - [ ] Run all existing integration tests
   - [ ] Run new cache handler tests
   - [ ] Run plugin integration tests

2. **Performance Benchmarking**
   - [ ] Measure API calls/minute (target: <20 vs 327 baseline)
   - [ ] Measure display update latency (target: <100ms vs 1-6s)
   - [ ] Measure CPU usage (target: <5% vs ~15%)
   - [ ] Measure memory usage (ensure no leaks)
   - [ ] Verify I2C bus conflicts eliminated

3. **Functional Validation**
   - [ ] All displays update correctly
   - [ ] Temperature readings accurate
   - [ ] Actor control works correctly
   - [ ] Mode switching works
   - [ ] Step transitions display properly
   - [ ] No data staleness issues

4. **Hardware Testing (Optional but Recommended)**
   - [ ] Test on dev Raspberry Pi (if available)
   - [ ] Verify I2C device communication
   - [ ] Check display rendering
   - [ ] Validate sensor readings
   - [ ] Test under load (simulated brewing)

5. **Code Quality**
   - [ ] All code follows project style (Black, isort)
   - [ ] No linting errors
   - [ ] Documentation complete and accurate
   - [ ] No TODO comments remaining
   - [ ] Code review (self-review)

6. **Create Validation Report**
   ```
   VALIDATION_REPORT.md:
   - Test results summary
   - Performance benchmarks
   - Known issues (if any)
   - Deployment recommendations
   - Rollback plan
   ```

#### Testing Checklist
- [ ] All 128+ existing tests pass
- [ ] All new cache handler tests pass (>80% coverage)
- [ ] All plugin integration tests pass
- [ ] Performance targets met
- [ ] No memory leaks detected
- [ ] No regression in functionality
- [ ] Backward compatibility verified

#### Completion Criteria
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Performance validated
- [ ] Validation report created
- [ ] Ready for deployment decision

---

## Pre-Merge Validation Checklist

Before merging to main, verify ALL of the following:

### Code Quality
- [ ] All code follows Black and isort formatting
- [ ] No linting errors (run `black . && isort .`)
- [ ] No debug print statements or commented code
- [ ] All TODO comments resolved or documented
- [ ] Code review completed (self-review)

### Testing
- [ ] All unit tests pass (128+ existing + new tests)
- [ ] All integration tests pass
- [ ] Test coverage >75% overall
- [ ] Cache handler coverage >80%
- [ ] No test warnings or deprecations

### Performance
- [ ] API calls reduced by >90% (target: 327 → <20/min)
- [ ] Display latency <100ms (vs 1-6s baseline)
- [ ] CPU usage <5% (vs ~15% baseline)
- [ ] Memory usage stable (no leaks)
- [ ] I2C bus conflicts eliminated

### Functionality
- [ ] All plugins initialize correctly
- [ ] Displays update in real-time
- [ ] Temperature readings accurate
- [ ] Actor control works
- [ ] Mode switching works
- [ ] Step transitions display properly
- [ ] No data staleness (cache TTL working)

### Documentation
- [ ] README.md updated with cache handler info
- [ ] CBPI4_DATA_ACCESS_ARCHITECTURE.md accurate
- [ ] DEPLOYMENT_STEPS.md followed completely
- [ ] API documentation complete
- [ ] Migration guide for plugins complete

### Backward Compatibility
- [ ] Old plugin API still works (if any unmigrated plugins)
- [ ] Configuration files compatible
- [ ] No breaking changes to CraftBeerPi4 integration

### Deployment Readiness
- [ ] Validation report created
- [ ] Known issues documented (if any)
- [ ] Rollback plan documented
- [ ] Deployment steps clear

---

## Deployment Day Plan

### Pre-Deployment (Morning)

1. **Final Testing Pass**
   ```bash
   python run_tests.py all
   ```
   - [ ] All tests pass
   - [ ] No warnings or errors

2. **Code Review**
   - [ ] Review all changes since branch creation
   - [ ] Verify no debug code or comments
   - [ ] Check commit messages are clear

3. **Create Deployment Commit**
   ```bash
   git add .
   git commit -m "Final validation before merge to main"
   git push
   ```

### Merge to Main

1. **Final Branch Sync**
   ```bash
   git checkout claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB
   git pull origin claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB
   ```

2. **Create Merge Commit**
   ```bash
   git checkout main
   git merge --no-ff claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB
   ```

3. **Verify Merge**
   ```bash
   python run_tests.py all
   git log --oneline -10
   ```

4. **Push to Main**
   ```bash
   git push origin main
   ```

### Post-Deployment

1. **Deploy to Production Pi**
   - [ ] Pull latest main branch
   - [ ] Install any new dependencies
   - [ ] Restart CraftBeerPi4 service
   - [ ] Verify all plugins load

2. **Initial Monitoring**
   - [ ] Check logs for errors
   - [ ] Verify displays update
   - [ ] Check sensor readings
   - [ ] Test mode switching
   - [ ] Monitor CPU/memory usage

3. **First Brew Session**
   - [ ] Monitor closely throughout brew
   - [ ] Check display accuracy
   - [ ] Verify step transitions
   - [ ] Note any issues
   - [ ] Collect performance data

4. **Keep Feature Branch**
   - **DO NOT DELETE** feature branch for 2-3 brew sessions
   - Allows easy rollback if issues found
   - Delete only after confirmed stability

---

## Rollback Plan

If issues are discovered after merge to main:

### Immediate Rollback (Critical Issues)

1. **Revert Merge Commit**
   ```bash
   git checkout main
   git log --oneline -10  # Find merge commit hash
   git revert -m 1 <merge-commit-hash>
   git push origin main
   ```

2. **Redeploy to Production Pi**
   ```bash
   git pull origin main
   sudo systemctl restart cbpi4
   ```

3. **Verify System Restored**
   - [ ] Check all plugins load
   - [ ] Verify displays work
   - [ ] Test brewing functionality

### Debug on Feature Branch

1. **Return to Feature Branch**
   ```bash
   git checkout claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB
   ```

2. **Reproduce and Fix Issue**
   - [ ] Add test case for bug
   - [ ] Fix issue
   - [ ] Verify fix with tests
   - [ ] Document issue and resolution

3. **Re-deployment Decision**
   - [ ] Complete additional testing
   - [ ] Update validation report
   - [ ] Attempt merge again when ready

---

## Progress Tracking

Use this section to track progress through each phase:

### Phase 1: Core Cache Handler
**Status**: Not Started
**Started**: [Date]
**Completed**: [Date]
**Notes**:

### Phase 2: Event Bus
**Status**: Not Started
**Started**: [Date]
**Completed**: [Date]
**Notes**:

### Phase 3: I2C Coordinator
**Status**: Not Started
**Started**: [Date]
**Completed**: [Date]
**Notes**:

### Phase 4: Main Cache Handler API
**Status**: Not Started
**Started**: [Date]
**Completed**: [Date]
**Notes**:

### Phase 5: Plugin Migration
**Status**: Not Started
**Started**: [Date]
**Completed**: [Date]
**Plugins Migrated**:
- [ ] 7SegDisplay
- [ ] LCDisplay
- [ ] BMT-Key
**Notes**:

### Phase 6: Integration Testing
**Status**: Not Started
**Started**: [Date]
**Completed**: [Date]
**Notes**:

### Deployment to Main
**Status**: Not Started
**Deployed**: [Date]
**First Brew**: [Date]
**Status After 3 Brews**: [Success/Issues]
**Notes**:

---

## Performance Targets

Track actual performance vs targets:

| Metric | Baseline | Target | Actual | Status |
|--------|----------|--------|--------|--------|
| API Calls/Min | 327 | <20 | - | - |
| Display Latency | 1-6s | <100ms | - | - |
| CPU Usage | ~15% | <5% | - | - |
| Memory Usage | Baseline | No increase | - | - |
| I2C Conflicts | Frequent | Zero | - | - |
| Test Coverage | 70% | 75% | - | - |

---

## Contact & Support

**Questions or Issues During Development?**
- Review CBPI4_DATA_ACCESS_ARCHITECTURE.md for design details
- Check test output for specific failures
- Review CraftBeerPi4 logs: `/var/log/cbpi4/`
- Test with hardware mocks before real hardware

**Post-Deployment Issues?**
- Check VALIDATION_REPORT.md
- Review rollback plan above
- Collect logs before reverting
- Document issues for future resolution

---

**Document Version**: 1.0
**Created**: 2025-11-16
**Branch**: `claude/docs-data-cache-handler-0176zAUiFmLSRcaZQPygf8YB`
**Status**: Planning - Ready to Begin Phase 1
