#!/bin/bash
# Run integration tests (matches CI integration-test job)

set -e

echo "=================================================="
echo "Integration Tests (matching CI)"
echo "=================================================="
echo ""

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Run integration tests
python3 -m pytest tests/integration/ \
    --verbose \
    --tb=short \
    --cov=tests/integration \
    --cov-report=xml \
    --cov-report=term-missing \
    -m "integration"

echo ""
echo "=================================================="
echo "Integration tests completed!"
echo "=================================================="
