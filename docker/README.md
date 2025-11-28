# Brewmotron Docker Testing Infrastructure

This directory contains Docker-based testing infrastructure for running Brewmotron tests and manual testing environments.

## Quick Start

### Automated Testing (Recommended)

Run the full test suite in an isolated Docker environment that matches the GitHub Actions CI/CD setup:

```bash
# Build the test image
docker build -f docker/Dockerfile.test -t brewmotron-test:latest .

# Run unit tests
docker run --rm brewmotron-test:latest python3 run_tests.py unit

# Run all tests
docker run --rm brewmotron-test:latest python3 run_tests.py all

# Run with custom pytest parameters
docker run --rm brewmotron-test:latest python3 -m pytest tests/unit/ -v --tb=short
```

### Manual Testing (Interactive CraftBeerPi4 Environment)

Start a full CraftBeerPi4 instance with all Brewmotron plugins for interactive testing:

```bash
# Start the manual test environment
docker-compose -f docker/docker-compose.yml up -d

# Access CraftBeerPi4 web interface at http://localhost:8000

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Stop the environment
docker-compose -f docker/docker-compose.yml down
```

## Why Use Docker?

- ✅ **Consistent Environment**: Matches GitHub Actions CI/CD exactly (Ubuntu 22.04 + Python 3.11)
- ✅ **Isolation**: No dependency conflicts with your local system
- ✅ **Reproducible**: Same results every time
- ✅ **Clean**: No system pollution - everything stays in containers
- ✅ **Fast Setup**: No need to install Python packages system-wide

## Test Environment Details

### Automated Testing (`Dockerfile.test`)
- **Base**: Ubuntu 22.04 LTS
- **Python**: 3.11.14
- **Purpose**: Run unit, integration, and hardware tests
- **Test Results**: 210+ tests with 85%+ code coverage
- **Execution Time**: ~12 seconds

### Manual Testing (`Dockerfile.manual-test`)
- **Base**: Ubuntu 22.04 LTS
- **Python**: 3.11
- **CraftBeerPi4**: Installed via pipx
- **Purpose**: Interactive web-based plugin testing
- **Access**: http://localhost:8000

## Advanced Usage

### Running Specific Test Types

```bash
# Unit tests only
docker run --rm brewmotron-test:latest python3 run_tests.py unit

# Hardware simulation tests
docker run --rm brewmotron-test:latest python3 run_tests.py hardware

# Integration tests
docker run --rm brewmotron-test:latest python3 run_tests.py integration
```

### Custom Branch Testing

Test a specific branch or fork:

```bash
# Set custom branch for manual testing
BRANCH_NAME=develop docker-compose -f docker/docker-compose.yml up -d
```

### Development Workflow

For active development, mount your local source code:

```bash
# Edit docker-compose.yml to uncomment:
# - .:/brewmotron:ro

# Then restart
docker-compose -f docker/docker-compose.yml up -d
```

## Test Coverage

Current test coverage (Phase 1 - Cache Handler Integration):

- **Active Tests**: 210 tests (cache handler + plugins)
- **Code Coverage**: 85%+ (cache handler module: 97%+)
- **Coverage Target**: 70% (exceeded)

## Troubleshooting

### Docker Build Fails

**Issue**: Cannot find requirements-test.txt
**Solution**: Ensure you're running from the repository root directory

**Issue**: Port 8000 already in use
**Solution**:
```bash
# Stop existing containers
docker-compose -f docker/docker-compose.yml down

# Or change port in docker-compose.yml
```

### Tests Hang or Timeout

Tests have automatic 10-second timeouts. If tests hang:
- Check for blocking I/O operations
- Verify mock objects are properly configured
- Review AsyncIO event loop cleanup

### Container Won't Start

Check logs:
```bash
docker-compose -f docker/docker-compose.yml logs brewmotron-cbpi4
```

## Files in This Directory

- **Dockerfile.test**: Automated testing environment
- **Dockerfile.manual-test**: Interactive CraftBeerPi4 environment
- **docker-compose.yml**: Manual test orchestration
- **docker-entrypoint.sh**: Container startup script for manual testing
- **init-manual-test.sh**: Plugin installation helper
- **README.md**: This file

## Relationship to GitHub Actions

This Docker infrastructure is independent from GitHub Actions CI/CD:

| Aspect | Docker (Local) | GitHub Actions (CI/CD) |
|--------|----------------|------------------------|
| **Trigger** | Manual (`docker build`) | Automatic (git push) |
| **Purpose** | Local development testing | Automated CI/CD pipeline |
| **Environment** | Ubuntu 22.04 + Python 3.11 | Ubuntu 22.04 + Python 3.10.12 |
| **Configuration** | `docker/` files | `.github/workflows/test.yml` |

Both environments are aligned but serve different purposes. Use Docker to validate changes before pushing to GitHub.

## Support

For more information:
- **Test Framework**: See root `run_tests.py`
- **GitHub Actions**: See `.github/workflows/test.yml`
- **Project Documentation**: See root `README.md`
