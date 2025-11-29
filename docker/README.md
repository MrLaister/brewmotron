# Brewmotron Docker Testing Infrastructure

This directory contains Docker-based testing infrastructure for running Brewmotron tests and manual testing environments.

## Purpose

- **Local Development Testing**: Run tests in isolated Docker containers that match the GitHub Actions environment
- **Raspberry Pi Validation**: ARM-based Raspbian testing with hardware library support
- **Manual Testing**: Full CraftBeerPi4 environment for interactive testing
- **Consistent Environments**: Reproducible test environments across platforms

## Files

- **Dockerfile.test**: Ubuntu 22.04 image for automated testing (CI/CD aligned)
- **Dockerfile.raspbian**: Debian Bullseye ARM64 image for Raspberry Pi-specific testing
- **Dockerfile.manual-test**: Docker image for interactive CraftBeerPi4 testing
- **docker-compose.yml**: Docker Compose configuration for all test environments
- **docker-entrypoint.sh**: Entrypoint script for manual test container
- **init-manual-test.sh**: Initialization script for manual test environment
- **MANUAL_TEST_DOCKER.md**: Detailed documentation for manual Docker testing

## Test Environment Comparison

| Feature | Ubuntu (Dockerfile.test) | Raspbian (Dockerfile.raspbian) |
|---------|-------------------------|--------------------------------|
| **Platform** | AMD64 (native) | ARM64 (QEMU emulation) |
| **OS** | Ubuntu 22.04 LTS | Debian Bullseye (Raspberry Pi OS) |
| **Python** | 3.11 | 3.9 (Debian default) |
| **Speed** | Fast (native execution) | Slower (QEMU overhead) |
| **Use Case** | CI/CD alignment, quick validation | RPi-specific interface testing |
| **Hardware Libs** | Mocked only | RPi.GPIO, smbus2, i2c-tools included |
| **GitHub Actions** | Matches exactly | N/A (local only) |

### When to Use Each Environment

**Ubuntu (Dockerfile.test)** - Default choice:
- ✅ Quick unit test validation
- ✅ Verifying GitHub Actions compatibility
- ✅ General Python compatibility testing
- ✅ Fast iteration during development

**Raspbian (Dockerfile.raspbian)** - Raspberry Pi validation:
- ✅ Testing RPi-specific library interfaces
- ✅ Validating hardware interface code
- ✅ OS-level compatibility verification
- ✅ Pre-deployment validation before deploying to actual RPi

## Quick Start

### Ubuntu-based Testing (Default - Fast)

```bash
# Build Ubuntu test image
docker build -f docker/Dockerfile.test -t brewmotron-test:latest .

# Run unit tests
docker run --rm brewmotron-test:latest python3 run_tests.py unit

# Run all tests
docker run --rm brewmotron-test:latest python3 run_tests.py all

# Using docker-compose
docker-compose -f docker/docker-compose.yml run --rm brewmotron-test-ubuntu
```

### Raspbian-based Testing (Raspberry Pi Validation)

**Note**: First time build will be slower due to QEMU emulation setup

```bash
# Enable Docker buildx for multi-platform support (one-time setup)
docker buildx create --use --name multiarch

# Build Raspbian test image (with ARM64 emulation)
docker buildx build --platform linux/arm64 \
  -f docker/Dockerfile.raspbian \
  -t brewmotron-test-raspbian:latest \
  --load .

# Run unit tests on Raspbian
docker run --rm brewmotron-test-raspbian:latest python3 run_tests.py unit

# Run all tests on Raspbian
docker run --rm brewmotron-test-raspbian:latest python3 run_tests.py all

# Using docker-compose (simpler)
docker-compose -f docker/docker-compose.yml build brewmotron-test-raspbian
docker-compose -f docker/docker-compose.yml run --rm brewmotron-test-raspbian
```

### Quick Test Script (Both Environments)

```bash
# Test on both platforms
./docker/test-all-platforms.sh

# Test on specific platform
./docker/test-all-platforms.sh ubuntu
./docker/test-all-platforms.sh raspbian
```

### Manual Testing (Interactive CraftBeerPi4 Environment)

Start a full CraftBeerPi4 instance with all Brewmotron plugins for interactive testing:

```bash
# Start manual test environment
docker-compose -f docker/docker-compose.yml up -d

# Access CraftBeerPi4 web interface
# http://localhost:8000

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Stop the environment
docker-compose -f docker/docker-compose.yml down
```

See `MANUAL_TEST_DOCKER.md` for detailed manual testing instructions.

## Why Use Docker?

- ✅ **Consistent Environment**: Matches GitHub Actions CI/CD exactly (Ubuntu 22.04 + Python 3.11)
- ✅ **Isolation**: No dependency conflicts with your local system
- ✅ **Reproducible**: Same results every time
- ✅ **Clean**: No system pollution - everything stays in containers
- ✅ **Fast Setup**: No need to install Python packages system-wide
- ✅ **Multi-Platform**: Test on both Ubuntu (AMD64) and Raspbian (ARM64)

## Test Environment Details

### Automated Testing (`Dockerfile.test`)
- **Base**: Ubuntu 22.04 LTS
- **Python**: 3.11.14
- **Purpose**: Run unit, integration, and hardware tests
- **Test Results**: 149+ tests with 94-97% code coverage
- **Execution Time**: ~10-11 seconds

### Raspbian Testing (`Dockerfile.raspbian`)
- **Base**: Debian Bullseye (Raspberry Pi OS)
- **Platform**: ARM64 via QEMU emulation
- **Python**: 3.9 (Debian default)
- **Purpose**: Raspberry Pi-specific validation
- **Hardware Libraries**: RPi.GPIO, smbus2, i2c-tools, adafruit-circuitpython packages
- **Performance**: 2-5x slower than native due to QEMU overhead

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

# Custom pytest parameters
docker run --rm brewmotron-test:latest python3 -m pytest tests/unit/ -v --tb=short
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

## QEMU Emulation on AMD64

The Raspbian Docker image uses QEMU to emulate ARM64 architecture on AMD64 hosts:

- **Setup**: Docker Desktop or Docker Engine with `binfmt_misc` support
- **Performance**: Slower than native execution (2-5x overhead typical)
- **Accuracy**: High - runs actual ARM binaries, not simulation
- **Use Case**: Pre-deployment validation without requiring physical Raspberry Pi hardware

### Enabling QEMU Support

```bash
# For Linux hosts (enable multi-architecture support)
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# Verify QEMU is available
docker buildx ls
```

Docker Desktop (Windows/Mac) includes QEMU support by default.

## Test Coverage

Current test coverage (Phase 1 - Cache Handler Integration):

- **Active Tests**: 149 tests (cache handler)
- **Code Coverage**: 94-97% (cache handler module: 97%+)
- **Coverage Target**: 70% (exceeded)
- **Test Execution Time**: ~10-11 seconds

### Phase 1/Phase 2 Staging

During **Phase 1** (cache handler integration), some tests are temporarily skipped:
- Plugin unit tests (86 tests) - marked with `@pytest.mark.skip`
- Integration tests (39 tests) - marked with `@pytest.mark.skip`
- Hardware simulation tests (112 tests) - marked with `@pytest.mark.skip`

Only cache handler unit tests are active (63 tests, 97%+ coverage).

See root `CLAUDE.md` for complete Phase 1/Phase 2 staging plan.

## Troubleshooting

### Docker Build Fails

**Issue**: Cannot find requirements-test.txt
**Solution**: Ensure you're running from the repository root directory

```bash
# Correct location (repository root)
docker build -f docker/Dockerfile.test -t brewmotron-test:latest .

# Wrong - do not run from docker/ directory
cd docker && docker build -f Dockerfile.test ...  # ❌ Don't do this
```

**Issue**: Port 8000 already in use
**Solution**:
```bash
# Stop existing containers
docker-compose -f docker/docker-compose.yml down

# Or change port in docker-compose.yml
```

**Issue**: "exec /bin/sh: exec format error" (Raspbian build)
**Solution**: Enable QEMU emulation
```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

### Tests Hang or Timeout

Tests have automatic 10-second timeouts. If tests hang:
- Check for blocking I/O operations
- Verify mock objects are properly configured
- Review AsyncIO event loop cleanup

### Container Won't Start

Check logs:
```bash
# Manual test container
docker-compose -f docker/docker-compose.yml logs brewmotron-cbpi4

# Test containers
docker logs brewmotron-test-ubuntu
docker logs brewmotron-test-raspbian
```

### Raspbian Build is Slow

This is expected behavior:
- First build: 5-10 minutes (QEMU emulation overhead)
- Subsequent builds: Use Docker layer caching
- Performance: 2-5x slower than native AMD64
- Consider: Use Ubuntu image for quick iterations, Raspbian for final validation

## Relationship to GitHub Actions

This Docker infrastructure is independent from GitHub Actions CI/CD:

| Aspect | Docker (Local) | GitHub Actions (CI/CD) |
|--------|----------------|------------------------|
| **Trigger** | Manual (`docker build`) | Automatic (git push) |
| **Purpose** | Local development testing | Automated CI/CD pipeline |
| **Environment** | Ubuntu 22.04 + Python 3.11 | Ubuntu 22.04 + Python 3.10.12 |
| **Configuration** | `docker/` files | `.github/workflows/test.yml` |
| **Platforms** | Ubuntu + Raspbian (ARM64) | Ubuntu only |

Both environments are aligned but serve different purposes. Use Docker to validate changes before pushing to GitHub.

## Test Results Reference

Last verified Docker test run:
- **149 tests PASSED** ✅
- **94-97% code coverage** ✅
- **Test execution time**: ~10-11 seconds

## Support

For more information:
- **Test Framework**: See root `run_tests.py`
- **Test Documentation**: See `tests/README.md`
- **GitHub Actions**: See `.github/workflows/test.yml`
- **Project Documentation**: See root `README.md`
