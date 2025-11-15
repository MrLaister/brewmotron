# Local Test Environment Setup

This directory contains scripts to set up and run a local test environment that mimics the CI/CD pipeline.

## Quick Start

### 1. Initial Setup

Run the setup script once to configure your environment:

```bash
./scripts/setup-test-env.sh
```

This script will:
- Check your Python version (requires Python 3.11)
- Install system dependencies (libgpiod2, python3-dev, build-essential)
- Set environment variables matching CI
- Install Python test dependencies from `requirements-test.txt`
- Verify the installation

### 2. Running Tests

After setup, you can run different test suites:

#### Run All CI Checks
```bash
./scripts/run-all-checks.sh
```

This runs all checks in sequence, matching the complete CI pipeline:
1. Code quality & linting
2. Unit tests
3. Integration tests
4. Hardware simulation tests

#### Run Individual Test Suites

**Linting and Code Quality:**
```bash
./scripts/run-lint.sh
```

Runs:
- Black code formatter check
- isort import sorting check
- flake8 linting (critical errors + advisory)
- mypy type checking (advisory)

**Unit Tests:**
```bash
./scripts/run-tests.sh
```

Runs unit tests with:
- Verbose output
- Coverage reporting (70% minimum)
- Excludes slow and integration tests

**Integration Tests:**
```bash
./scripts/run-integration-tests.sh
```

Runs integration tests marked with the `integration` marker.

**Hardware Simulation Tests:**
```bash
./scripts/run-hardware-tests.sh
```

Runs hardware simulation tests with 5-minute timeout.

To generate an HTML report:
```bash
./scripts/run-hardware-tests.sh --report
```

## Environment Details

### System Requirements

The test environment matches the CI configuration:

- **OS**: Ubuntu 22.04 LTS (or compatible Debian-based system)
- **Python**: 3.11
- **System packages**:
  - libgpiod2 (GPIO library)
  - python3-dev (Python development headers)
  - build-essential (Compilation tools)

### Environment Variables

The following environment variables are set (matching CI):

```bash
PYTHONUNBUFFERED=1          # Unbuffered Python output
PYTHONDONTWRITEBYTECODE=1   # Don't create .pyc files
```

### Python Dependencies

All dependencies are defined in `requirements-test.txt` including:

- **Testing frameworks**: pytest, pytest-asyncio, pytest-cov, pytest-mock
- **Code quality**: black, flake8, isort, mypy
- **Mocking**: mock, factory-boy, freezegun, responses
- **Hardware simulation**: fake-rpi
- **Performance**: memory-profiler, py-spy

## Test Organization

Tests are organized by type and markers:

### Test Directories
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests

### Test Markers
- `integration` - Integration tests
- `hardware` - Hardware simulation tests
- `slow` - Performance/slow tests

### Running Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/unit/ -m "not slow and not integration"

# Integration tests only
pytest tests/integration/ -m "integration"

# Hardware tests only
pytest tests/ -m "hardware"

# All tests including slow ones
pytest tests/
```

## CI/CD Comparison

### What's Included

These scripts replicate the following CI jobs:

- ✅ **lint**: Code quality and linting checks
- ✅ **test**: Unit tests with coverage
- ✅ **integration-test**: Integration tests
- ✅ **hardware-test**: Hardware simulation tests

### What's Not Included

The following CI jobs are not replicated locally:

- ❌ **security**: Security scanning (safety, bandit)
- ❌ **docs-test**: Documentation validation
- ❌ **build-test**: Package building
- ❌ **performance-test**: Performance benchmarking (runs on schedule only)

To run these, refer to the individual commands in `.github/workflows/test.yml`.

## Troubleshooting

### Python Version Mismatch

If you don't have Python 3.11:

1. **Using pyenv** (recommended):
   ```bash
   pyenv install 3.11.14
   pyenv local 3.11.14
   ```

2. **Using system package manager**:
   ```bash
   sudo apt-get install python3.11 python3.11-dev
   ```

### System Dependencies

If `apt-get` is not available (non-Debian systems), manually install equivalents:

- **libgpiod2**: GPIO library for hardware interaction
- **python3-dev**: Python development headers for compiling extensions
- **build-essential**: GCC, make, and other build tools

### Permission Issues

If you get permission errors:

```bash
# Make scripts executable
chmod +x ./scripts/*.sh

# Or run with bash explicitly
bash ./scripts/setup-test-env.sh
```

### Coverage Reports

Coverage reports are generated in multiple formats:

- `coverage.xml` - XML format (for CI integration)
- Terminal output - Human-readable summary
- HTML report (optional): `coverage html` then open `htmlcov/index.html`

## Continuous Integration Workflow

The CI pipeline (`.github/workflows/test.yml`) runs:

1. **On every push** to `main` or `develop`: lint, test, integration-test, hardware-test
2. **On every PR** to `main`: Full test suite
3. **Daily at 2 AM UTC**: Full suite including performance tests
4. **Manual trigger**: Full suite including performance tests

## Additional Scripts

### Security Scanning

```bash
# Install security tools
pip install safety bandit

# Run safety check
safety check --json --output safety-report.json

# Run bandit security linter
bandit -r . -f json -o bandit-report.json
```

### Documentation Testing

```bash
# Check README exists and has content
[ -f "README.md" ] && echo "README found" || echo "README missing"

# Check docstring coverage (from CI)
python -c "import ast, os; ..." # See .github/workflows/test.yml:324-357
```

### Build Testing

```bash
# Install build tools
pip install build twine

# Build packages
for plugin_dir in cbpi4-*; do
  [ -d "$plugin_dir" ] && [ -f "$plugin_dir/setup.py" ] && (
    cd "$plugin_dir"
    python -m build --wheel --outdir ../dist/
    cd ..
  )
done

# Validate packages
twine check dist/*.whl
```

## Best Practices

1. **Run locally before pushing**: Use `./scripts/run-all-checks.sh` to catch issues early
2. **Fix linting first**: Linting errors block other tests in CI
3. **Maintain coverage**: Unit tests require 70% coverage minimum
4. **Use markers**: Tag tests appropriately (integration, hardware, slow)
5. **Keep CI in sync**: Update these scripts when modifying `.github/workflows/test.yml`

## Getting Help

- Check the CI configuration: `.github/workflows/test.yml`
- Review test requirements: `requirements-test.txt`
- Check pytest configuration: `pyproject.toml` or `pytest.ini`
- Review code style config: `.flake8`, `pyproject.toml`

## Maintenance

When updating the CI pipeline:

1. Update `.github/workflows/test.yml`
2. Update corresponding script in `scripts/`
3. Update this README if needed
4. Test locally before committing
