#!/bin/bash
#
# Pre-submission validation script
# Checks all requirements from the hackathon checklist
# Usage: ./validate.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FAILED=0
PASSED=0

check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  NegotiationRL - Pre-Submission Validation               ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Check inference.py exists at root
echo -e "${YELLOW}[1/10]${NC} Checking inference.py location..."
if [ -f "inference.py" ]; then
    check_pass "inference.py exists at repo root"
else
    check_fail "inference.py not found at repo root"
fi
echo ""

# 2. Check .env file
echo -e "${YELLOW}[2/10]${NC} Checking .env configuration..."
if [ -f ".env" ]; then
    check_pass ".env file exists"
    
    # Check required variables
    grep -q "API_BASE_URL" .env && check_pass "API_BASE_URL defined" || check_warn "API_BASE_URL not in .env (will use default)"
    grep -q "MODEL_NAME" .env && check_pass "MODEL_NAME defined" || check_warn "MODEL_NAME not in .env (will use default)"
    grep -q "HF_TOKEN" .env && check_pass "HF_TOKEN defined" || check_fail "HF_TOKEN not in .env"
    grep -q "IMAGE_NAME" .env && check_pass "IMAGE_NAME defined" || check_fail "IMAGE_NAME not in .env"
else
    check_fail ".env file not found"
    echo -e "  ${YELLOW}Create .env with: API_BASE_URL, MODEL_NAME, HF_TOKEN, IMAGE_NAME${NC}"
fi
echo ""

# 3. Check openenv.yaml
echo -e "${YELLOW}[3/10]${NC} Checking openenv.yaml..."
if [ -f "openenv.yaml" ]; then
    check_pass "openenv.yaml exists"
    
    # Check for 3 tasks
    task_count=$(grep -c "^  - name:" openenv.yaml || echo 0)
    if [ "$task_count" -eq 3 ]; then
        check_pass "3 tasks defined"
    else
        check_fail "Expected 3 tasks, found $task_count"
    fi
    
    # Check for grader functions
    grep -q "fn: negotiation_env.graders:" openenv.yaml && check_pass "Grader functions referenced" || check_fail "Grader functions not properly referenced"
else
    check_fail "openenv.yaml not found"
fi
echo ""

# 4. Check Dockerfile
echo -e "${YELLOW}[4/10]${NC} Checking Dockerfile..."
if [ -f "negotiation_env/server/Dockerfile" ]; then
    check_pass "Dockerfile exists"
    
    grep -q 'PYTHONPATH="/app"' negotiation_env/server/Dockerfile && check_pass "PYTHONPATH correctly configured" || check_fail "PYTHONPATH may be incorrect"
else
    check_fail "Dockerfile not found"
fi
echo ""

# 5. Check graders.py
echo -e "${YELLOW}[5/10]${NC} Checking grader functions..."
if [ -f "negotiation_env/graders.py" ]; then
    check_pass "graders.py exists"
    grep -q "def grade_easy_conceder" negotiation_env/graders.py && check_pass "grade_easy_conceder defined"
    grep -q "def grade_medium_tft" negotiation_env/graders.py && check_pass "grade_medium_tft defined"
    grep -q "def grade_hard_hardliner" negotiation_env/graders.py && check_pass "grade_hard_hardliner defined"
else
    check_fail "graders.py not found"
fi
echo ""

# 6. Check imports in inference.py
echo -e "${YELLOW}[6/10]${NC} Checking inference.py imports..."
grep -q "from openai import OpenAI" inference.py && check_pass "Uses OpenAI client" || check_fail "OpenAI client not imported"
grep -q "from negotiation_env import" inference.py && check_pass "Imports negotiation_env package" || check_fail "negotiation_env import missing"
echo ""

# 7. Check log format
echo -e "${YELLOW}[7/10]${NC} Checking stdout log format..."
(grep -q '\[START\]' inference.py && grep -q '\[STEP\]' inference.py && grep -q '\[END\]' inference.py) && check_pass "[START], [STEP], [END] log format implemented" || check_fail "Log format not properly implemented"
grep -q 'score:.3f' inference.py && check_pass "Score uses .3f format" || check_fail "Score format incorrect (should be .3f)"
echo ""

# 8. Run tests
echo -e "${YELLOW}[8/10]${NC} Running test suite..."
if uv run pytest negotiation_env/test_env.py -q > /dev/null 2>&1; then
    check_pass "All tests passing"
else
    check_fail "Some tests failing"
fi
echo ""

# 9. Check Python imports work
echo -e "${YELLOW}[9/10]${NC} Checking Python imports..."
if uv run python -c "from negotiation_env import NegotiationEnv, NegotiationAction; from negotiation_env import grade_easy_conceder" > /dev/null 2>&1; then
    check_pass "All imports working"
else
    check_fail "Import errors detected"
fi
echo ""

# 10. Check README
echo -e "${YELLOW}[10/10]${NC} Checking documentation..."
if [ -f "README.md" ]; then
    check_pass "README.md exists"
    grep -q "your-username" README.md && check_warn "Placeholder 'your-username' still in README" || true
    grep -q "YOUR_HF_USERNAME" README.md && check_fail "Template placeholder 'YOUR_HF_USERNAME' still in README" || true
else
    check_fail "README.md not found"
fi
echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Passed:${NC} $PASSED checks"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed:${NC} $FAILED checks"
    echo ""
    echo -e "${RED}⚠  Fix the failed checks before submitting!${NC}"
    exit 1
else
    echo -e "${GREEN}Failed:${NC} 0 checks"
    echo ""
    echo -e "${GREEN}✓  All validation checks passed!${NC}"
    echo -e "${GREEN}✓  Ready for submission.${NC}"
    exit 0
fi
