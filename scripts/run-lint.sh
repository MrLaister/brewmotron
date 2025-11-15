#!/bin/bash
# Run linting checks (matches CI lint job)

set -e

echo "=================================================="
echo "Code Quality & Linting (matching CI)"
echo "=================================================="
echo ""

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

run_check() {
    local name=$1
    shift
    echo "Running $name..."
    if "$@"; then
        echo -e "${GREEN}✓ $name passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}"
        echo ""
        return 1
    fi
}

failures=0

# Black code formatter check
run_check "Black code formatter" \
    black --check --diff --color . || ((failures++))

# isort import sorting check
run_check "isort import sorting" \
    isort --check-only --diff . || ((failures++))

# flake8 linting - critical errors
echo "Running flake8 (critical errors)..."
if flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics; then
    echo -e "${GREEN}✓ flake8 critical errors passed${NC}"
    echo ""
else
    echo -e "${RED}✗ flake8 critical errors failed${NC}"
    echo ""
    ((failures++))
fi

# flake8 linting - full check (non-blocking)
echo "Running flake8 (full linting - advisory)..."
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=128 \
    --extend-ignore=E203,E501,W503,W504 --statistics
echo ""

# mypy type checking (advisory)
echo "Running mypy type checking (advisory)..."
mypy . --ignore-missing-imports --python-version=3.11 || true
echo ""

echo "=================================================="
if [ $failures -eq 0 ]; then
    echo -e "${GREEN}All linting checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$failures check(s) failed${NC}"
    exit 1
fi
