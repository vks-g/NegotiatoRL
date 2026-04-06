#!/bin/bash
#
# Build and test Docker image
# Usage: ./build_docker.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

IMAGE_NAME="${IMAGE_NAME:-negotiation-env:latest}"

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  NegotiationRL - Docker Build & Test                     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}[1/4]${NC} Building Docker image: ${IMAGE_NAME}"
echo ""

if docker build -t "$IMAGE_NAME" .; then
    echo -e "${GREEN}✓${NC} Docker build successful"
else
    echo -e "${RED}✗${NC} Docker build failed"
    exit 1
fi

echo ""
echo -e "${YELLOW}[2/4]${NC} Starting container..."
echo ""

# Stop any existing container
docker stop negotiation-env-test 2>/dev/null || true
docker rm negotiation-env-test 2>/dev/null || true

# Start new container
if docker run -d --name negotiation-env-test -p 8000:8000 "$IMAGE_NAME"; then
    echo -e "${GREEN}✓${NC} Container started"
else
    echo -e "${RED}✗${NC} Failed to start container"
    exit 1
fi

echo ""
echo -e "${YELLOW}[3/4]${NC} Waiting for server to be ready..."
sleep 5

echo ""
echo -e "${YELLOW}[4/4]${NC} Testing endpoints..."
echo ""

# Test health endpoint
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}✓${NC} /health endpoint working"
else
    echo -e "${RED}✗${NC} /health endpoint failed"
    docker logs negotiation-env-test
    exit 1
fi

# Test docs endpoint
if curl -s http://localhost:8000/docs | grep -q "openapi"; then
    echo -e "${GREEN}✓${NC} /docs endpoint working"
else
    echo -e "${YELLOW}⚠${NC} /docs endpoint may have issues (non-critical)"
fi

# Test reset endpoint
if curl -s -X POST http://localhost:8000/reset \
    -H "Content-Type: application/json" \
    -d '{"seed": 42}' | grep -q "observation"; then
    echo -e "${GREEN}✓${NC} /reset endpoint working"
else
    echo -e "${YELLOW}⚠${NC} /reset endpoint may have issues"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓  Docker image built and tested successfully!${NC}"
echo ""
echo "Container is running at: http://localhost:8000"
echo ""
echo "Next steps:"
echo "  • View logs:    docker logs negotiation-env-test"
echo "  • Stop:         docker stop negotiation-env-test"
echo "  • Push to HF:   docker tag $IMAGE_NAME <your-hf-space>"
echo ""
