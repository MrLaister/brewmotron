#!/bin/bash
# Run hardware simulation tests (matches CI hardware-test job)

set -e

echo "=================================================="
echo "Hardware Simulation Tests (matching CI)"
echo "=================================================="
echo ""

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Run hardware simulation tests
pytest tests/ \
    --verbose \
    --tb=short \
    -m "hardware" \
    --timeout=300

# Generate HTML report (optional)
if [ "$1" == "--report" ]; then
    echo ""
    echo "Generating HTML report..."
    pytest tests/ \
        -m "hardware" \
        --html=hardware-test-report.html \
        --self-contained-html || true
    echo "Report saved to: hardware-test-report.html"
fi

echo ""
echo "=================================================="
echo "Hardware tests completed!"
echo "=================================================="
