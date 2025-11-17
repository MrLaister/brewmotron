# Brewmotron Cache Handler - TODO

This file tracks planned enhancements and future work for the brewmotron cache handler.

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

### Low Priority

- [ ] **Cache Warming on Startup**
  - Pre-fetch all cache types when cbpi4 starts
  - Reduce first-access latency
  - Warm cache immediately after singleton initialization

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

**Last Updated**: 2025-11-16
**Maintained By**: MrLaister
