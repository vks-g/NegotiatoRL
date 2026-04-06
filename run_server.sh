#!/bin/bash
#
# Start the NegotiationEnv server locally
# Usage: ./run_server.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  NegotiationRL - Local Server                            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Starting server at http://localhost:8000${NC}"
echo ""
echo "Available endpoints:"
echo "  • http://localhost:8000/health"
echo "  • http://localhost:8000/docs"
echo "  • http://localhost:8000/reset"
echo "  • http://localhost:8000/state"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Run server using uv
exec uv run server
