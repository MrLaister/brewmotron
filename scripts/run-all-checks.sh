#!/bin/bash
# Run all CI checks locally

set +e  # Don't exit on error, we want to run all checks

echo "=================================================="
echo "Running All CI Checks Locally"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failures=0
total=0

run_check() {
    local name=$1
    local script=$2

    echo ""
    echo "=================================================="
    echo "Running: $name"
    echo "=================================================="
    ((total++))

    if bash "$SCRIPT_DIR/$script"; then
        echo -e "${GREEN}✓ $name PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ $name FAILED${NC}"
        ((failures++))
        return 1
    fi
}

# Run all checks in order (matching CI job dependencies)
run_check "Code Quality & Linting" "run-lint.sh"
run_check "Unit Tests" "run-tests.sh"
run_check "Integration Tests" "run-integration-tests.sh"
run_check "Hardware Tests" "run-hardware-tests.sh"

# Summary
echo ""
echo "=================================================="
echo "Test Results Summary"
echo "=================================================="
echo ""
echo "Total checks: $total"
echo -e "Passed: ${GREEN}$((total - failures))${NC}"
echo -e "Failed: ${RED}$failures${NC}"
echo ""

if [ $failures -eq 0 ]; then
    echo -e "${GREEN}=================================================="
    echo "✅ All checks passed!"
    echo "=================================================="
    echo -e "${NC}"
    exit 0
else
    echo -e "${RED}=================================================="
    echo "❌ Some checks failed"
    echo "=================================================="
    echo -e "${NC}"
    echo "Please review the output above to see which checks failed."
    exit 1
fi
