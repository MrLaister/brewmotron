#!/bin/bash
# Brewmotron Local Test Environment Setup
# This script mimics the CI environment setup for local testing

set -e  # Exit on error

echo "=================================================="
echo "Brewmotron Local Test Environment Setup"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

print_error() {
    echo -e "${RED}Error:${NC} $1"
}

# Check Python version
print_step "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
REQUIRED_VERSION="3.11"

if [ "$PYTHON_VERSION" != "$REQUIRED_VERSION" ]; then
    print_warning "Python $PYTHON_VERSION detected. CI uses Python $REQUIRED_VERSION"
    print_warning "Tests may behave differently. Consider using pyenv or similar."
else
    echo "Python $PYTHON_VERSION detected - matches CI environment ✓"
fi
echo ""

# Install system dependencies (matching CI)
print_step "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    # Try to install packages, but don't fail if sudo isn't available
    if sudo -n true 2>/dev/null; then
        echo "Updating package lists..."
        sudo apt-get update -qq 2>/dev/null || true

        echo "Installing packages: libgpiod2, python3-dev, build-essential"
        sudo apt-get install -y --no-install-recommends \
            libgpiod2 \
            python3-dev \
            build-essential 2>/dev/null || {
                print_warning "Could not install system packages. They may already be installed."
            }
        echo "System dependencies check completed ✓"
    else
        print_warning "sudo not available or requires password."
        print_warning "Skipping system package installation."
        print_warning "Required packages: libgpiod2, python3-dev, build-essential"

        # Check if packages are already available
        echo "Checking for existing packages..."
        dpkg -l | grep -q "build-essential" && echo "  ✓ build-essential found"
        dpkg -l | grep -q "python3-dev" && echo "  ✓ python3-dev found"
        dpkg -l | grep -q "libgpiod2" && echo "  ✓ libgpiod2 found" || echo "  ✗ libgpiod2 not found (may cause issues)"
    fi
else
    print_warning "apt-get not found. This script is designed for Debian/Ubuntu systems."
    print_warning "Please manually install: libgpiod2, python3-dev, build-essential"
fi
echo ""

# Set environment variables (matching CI)
print_step "Setting environment variables..."
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
echo "PYTHONUNBUFFERED=1"
echo "PYTHONDONTWRITEBYTECODE=1"
echo "Environment variables set ✓"
echo ""

# Upgrade pip
print_step "Upgrading pip..."
if python3 -m pip install --upgrade pip --quiet 2>/dev/null; then
    echo "pip upgraded ✓"
else
    print_warning "Could not upgrade pip. Using existing version: $(pip --version)"
fi
echo ""

# Install Python test dependencies
print_step "Installing Python test dependencies..."
if [ ! -f "requirements-test.txt" ]; then
    print_error "requirements-test.txt not found!"
    exit 1
fi

pip install -r requirements-test.txt
echo "Python dependencies installed ✓"
echo ""

# Create cache directory (matching CI cache structure)
print_step "Setting up cache directories..."
mkdir -p .cache/pip
echo "Cache directories created ✓"
echo ""

# Verify installation
print_step "Verifying installation..."
echo "Checking critical packages..."

packages=("pytest" "black" "flake8" "isort" "mypy")
all_installed=true

for package in "${packages[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo "  ✓ $package"
    else
        echo "  ✗ $package"
        all_installed=false
    fi
done

echo ""

if [ "$all_installed" = true ]; then
    echo -e "${GREEN}=================================================="
    echo "Setup completed successfully!"
    echo "=================================================="
    echo ""
    echo "Next steps:"
    echo "  1. Run tests: ./scripts/run-tests.sh"
    echo "  2. Run linting: ./scripts/run-lint.sh"
    echo "  3. Run all CI checks: ./scripts/run-all-checks.sh"
    echo -e "${NC}"
else
    print_error "Some packages failed to install. Please check the output above."
    exit 1
fi
