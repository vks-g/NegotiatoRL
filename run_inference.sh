#!/bin/bash
#
# Run inference.py with proper environment setup
# Usage: ./run_inference.sh [task_name]
#
# Examples:
#   ./run_inference.sh                    # Run all 3 tasks (local testing)
#   ./run_inference.sh easy_conceder      # Run only easy task
#   ./run_inference.sh medium_tft         # Run only medium task
#   ./run_inference.sh hard_hardliner     # Run only hard task

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  NegotiationRL - Inference Script Runner                 ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} Loading environment variables from .env"
    set -a
    source .env
    set +a
else
    echo -e "${YELLOW}⚠${NC}  No .env file found. Using environment defaults."
fi

# Validate required environment variables
MISSING_VARS=()

if [ -z "${API_BASE_URL:-}" ]; then
    echo -e "${YELLOW}⚠${NC}  API_BASE_URL not set. Using default: https://router.huggingface.co/v1"
    export API_BASE_URL="https://router.huggingface.co/v1"
fi

if [ -z "${MODEL_NAME:-}" ]; then
    echo -e "${YELLOW}⚠${NC}  MODEL_NAME not set. Using default: Qwen/Qwen2.5-72B-Instruct"
    export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
fi

if [ -z "${HF_TOKEN:-}" ] && [ -z "${API_KEY:-}" ]; then
    MISSING_VARS+=("HF_TOKEN or API_KEY")
fi

if [ -z "${IMAGE_NAME:-}" ]; then
    MISSING_VARS+=("IMAGE_NAME")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}✗${NC} Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "  ${RED}•${NC} $var"
    done
    echo ""
    echo "Please set these variables in .env or export them:"
    echo "  export HF_TOKEN=your-token-here"
    echo "  export IMAGE_NAME=your-docker-image-name"
    echo ""
    exit 1
fi

# Set task name if provided
if [ $# -gt 0 ]; then
    export NEGOTIATION_TASK="$1"
    echo -e "${GREEN}✓${NC} Running single task: ${YELLOW}$1${NC}"
else
    echo -e "${GREEN}✓${NC} Running all tasks (local testing mode)"
fi

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "  API_BASE_URL: ${YELLOW}${API_BASE_URL}${NC}"
echo -e "  MODEL_NAME:   ${YELLOW}${MODEL_NAME}${NC}"
echo -e "  IMAGE_NAME:   ${YELLOW}${IMAGE_NAME}${NC}"
echo -e "  HF_TOKEN:     ${YELLOW}${HF_TOKEN:0:10}...${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Run inference.py using uv
exec uv run --project negotiation_env python3 inference.py
