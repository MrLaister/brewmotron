#!/bin/bash
# Brewmotron Manual Test Initialization Script
# Pulls fresh code from GitHub, wipes container, and rebuilds from scratch

set -e

# Default values
GITHUB_REPO="https://github.com/MrLaister/brewmotron.git"
BRANCH_NAME="main"
CONTAINER_NAME="brewmotron-cbpi4"
IMAGE_NAME="brewmotron-manual-test"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Initialize fresh Brewmotron manual test environment from GitHub

OPTIONS:
    -b, --branch BRANCH     Git branch to use (default: main)
    -r, --repo URL          GitHub repository URL (default: MrLaister/brewmotron)
    -h, --help              Show this help message

EXAMPLES:
    # Use main branch
    $0

    # Use feature branch
    $0 --branch feature/new-plugin

    # Use different repository
    $0 --repo https://github.com/user/fork.git --branch dev

WHAT THIS SCRIPT DOES:
    1. Stops and removes existing container
    2. Removes configuration volumes (fresh start)
    3. Clones code from specified GitHub branch
    4. Builds fresh Docker image with cbpi4 and plugins
    5. Starts new container with plugins installed
    6. Container accessible at http://localhost:8000

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--branch)
            BRANCH_NAME="$2"
            shift 2
            ;;
        -r|--repo)
            GITHUB_REPO="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

echo ""
echo "=========================================="
echo "  Brewmotron Manual Test Initialization"
echo "=========================================="
echo "Repository: $GITHUB_REPO"
echo "Branch:     $BRANCH_NAME"
echo "=========================================="
echo ""

# Step 1: Stop and remove existing container
print_step "Stopping existing container (if running)..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
    print_step "Container removed"
else
    print_step "No existing container found"
fi

# Step 2: Remove volumes for fresh configuration
print_step "Removing configuration volumes for fresh start..."
docker volume rm brewmotron-config 2>/dev/null || print_step "No existing volume to remove"

# Step 3: Remove old image
print_step "Removing old Docker image..."
docker rmi ${IMAGE_NAME}:latest 2>/dev/null || print_step "No existing image to remove"

# Step 4: Build new image from GitHub
print_step "Building fresh Docker image from GitHub branch '${BRANCH_NAME}'..."
docker build \
    --no-cache \
    --build-arg GITHUB_REPO="${GITHUB_REPO}" \
    --build-arg BRANCH_NAME="${BRANCH_NAME}" \
    -f Dockerfile.manual-test \
    -t ${IMAGE_NAME}:latest \
    .

if [ $? -ne 0 ]; then
    print_error "Docker build failed!"
    exit 1
fi

print_step "Docker image built successfully"

# Step 5: Start new container with plugins
print_step "Starting fresh container with plugin installation..."
docker run -d \
    --name ${CONTAINER_NAME} \
    -p 8000:8000 \
    -e INSTALL_PLUGINS=true \
    -e CBPI_CONFIG_FOLDER=/cbpi_config \
    -v brewmotron-config:/cbpi_config \
    ${IMAGE_NAME}:latest

if [ $? -ne 0 ]; then
    print_error "Failed to start container!"
    exit 1
fi

print_step "Container started successfully"

# Step 6: Wait for container to be ready
print_step "Waiting for CraftBeerPi4 to initialize..."
sleep 5

# Step 7: Show status
echo ""
echo "=========================================="
echo -e "${GREEN}✓ Initialization Complete!${NC}"
echo "=========================================="
echo ""
echo "Container Status:"
docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "Access Points:"
echo "  Web Interface: http://localhost:8000"
echo ""
echo "Useful Commands:"
echo "  View logs:     docker logs -f ${CONTAINER_NAME}"
echo "  Enter shell:   docker exec -it ${CONTAINER_NAME} bash"
echo "  Stop:          docker stop ${CONTAINER_NAME}"
echo "  Restart:       docker restart ${CONTAINER_NAME}"
echo ""
echo "To reinitialize with different branch:"
echo "  ./init-manual-test.sh --branch <branch-name>"
echo ""
echo "=========================================="

# Show initial logs
print_step "Initial startup logs:"
docker logs ${CONTAINER_NAME}
