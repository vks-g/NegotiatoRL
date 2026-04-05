#!/bin/bash
#
# Run tests for NegotiationRL
# Usage: ./run_tests.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT/negotiation_env"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  NegotiationRL - Test Suite                              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Running all tests...${NC}"
echo ""

# Run pytest with verbose output
uv run pytest negotiation_env/test_env.py -v --tb=short

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
