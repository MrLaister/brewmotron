#!/bin/bash
# Run unit tests (matches CI test job)

set -e

echo "=================================================="
echo "Unit Tests (matching CI)"
echo "=================================================="
echo ""

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Run unit tests with coverage
python3 -m pytest tests/unit/ \
    --verbose \
    --tb=short \
    --cov=tests/unit \
    --cov-report=xml \
    --cov-report=term-missing \
    --cov-fail-under=70 \
    -m "not slow and not integration"

echo ""
echo "=================================================="
echo "Unit tests completed!"
echo "Coverage report saved to: coverage.xml"
echo "=================================================="
