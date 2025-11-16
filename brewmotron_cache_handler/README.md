# Brewmotron Cache Handler

High-performance caching layer for CraftBeerPi4 data access.

## Overview

The cache handler reduces excessive API polling from ~327 calls/minute to <20 calls/minute through intelligent TTL-based caching and event-driven updates.

## Phase 1: Core Cache (Current)

### Components

#### `CacheEntry`
Data model for cache entries with TTL support.

**Features:**
- Automatic expiration validation
- Age tracking
- Refresh capability
- Serialization support

**Example:**
```python
from brewmotron_cache_handler import CacheEntry

entry = CacheEntry(
    data={"temperature": 65.5},
    ttl=0.5,  # 500ms
    cache_type="sensor"
)

if entry.is_valid():
    print(f"Data: {entry.data}")
else:
    print(f"Expired {entry.age():.2f}s ago")
```

#### `DataCache`
Multi-cache store with automatic TTL-based expiration.

**Features:**
- Separate caches for step, kettle, sensor, actor, config
- Configurable TTL per cache type
- Async-safe with locking
- Statistics tracking
- Force refresh support

**Default TTL Values:**
- Step: 500ms (fast-changing during brewing)
- Kettle: 1000ms (moderate changes)
- Sensor: 500ms (frequent updates)
- Actor: 250ms (rapid state changes)
- Config: 60s (rarely changes)

**Example:**
```python
from brewmotron_cache_handler import DataCache, CacheType

cache = DataCache(cbpi)

# Fetch with automatic caching
async def fetch_step_data():
    return cbpi.step.get_state()

data = await cache.get(CacheType.STEP, fetch_func=fetch_step_data)

# Force refresh
data = await cache.get(CacheType.STEP, fetch_func=fetch_step_data, force_refresh=True)

# Check statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

## Future Phases

### Phase 2: Event Bus (Coming Soon)
- Pub/sub event system
- Real-time state change notifications
- Event history tracking

### Phase 3: I2C Coordinator (Coming Soon)
- Queue-based I2C bus access
- Priority scheduling
- Deadlock prevention

### Phase 4: Main API (Coming Soon)
- Unified CBPI4CacheHandler facade
- Plugin-friendly API
- Backward compatibility layer

## Performance Targets

| Metric | Baseline | Target | Phase 1 |
|--------|----------|--------|---------|
| API Calls/Min | 327 | <20 | N/A (Phase 4) |
| Cache Hit Rate | 0% | >90% | Measured |
| Memory Overhead | 0MB | <10MB | <1MB |

## Testing

Run cache handler tests:
```bash
pytest tests/unit/test_cache_handler/ -v
```

Run with coverage:
```bash
pytest tests/unit/test_cache_handler/ --cov=brewmotron_cache_handler --cov-report=html
```

## Development Status

**Phase 1**: ✅ Complete (Core cache with TTL)
**Phase 2**: 🔄 In Progress (Event bus)
**Phase 3**: ⏳ Pending (I2C coordinator)
**Phase 4**: ⏳ Pending (Main API)
**Phase 5**: ⏳ Pending (Plugin migration)
**Phase 6**: ⏳ Pending (Integration testing)

## Documentation

- Architecture: `../CBPI4_DATA_ACCESS_ARCHITECTURE.md`
- Deployment Plan: `../DEPLOYMENT_STEPS.md`
- API Reference: See docstrings in source files
