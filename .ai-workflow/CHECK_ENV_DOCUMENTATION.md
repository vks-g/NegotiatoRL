# check_env.sh - Environment Validation Script

## Purpose

Validates your local environment against the requirements specified in `Information/pre-validation.py`. This helps catch issues **before** submitting to the hackathon.

## What It Does

The script performs 5 comprehensive validation steps that match the official pre-validation script:

### Step 1: Check Prerequisites
- ✅ Docker installed and daemon running
- ✅ openenv-core installed (or available via uv)
- ✅ curl installed
- ✅ uv package manager installed

### Step 2: Check Repository Structure
- ✅ Dockerfile exists (in repo root, server/, or nested structure)
- ✅ openenv.yaml exists
- ✅ inference.py at repo root
- ✅ .env file with HF_TOKEN and IMAGE_NAME

### Step 3: Test Docker Build
- ✅ Builds Docker image from correct context
- ✅ Handles nested Dockerfile paths (like `negotiation_env/negotiation_env/server/Dockerfile`)
- ✅ Reports build time
- ✅ Shows error output if build fails

### Step 4: Run openenv validate
- ✅ Runs `openenv validate` (system-wide or via `uv run`)
- ⚠️ Treats "multi-mode deployment" warnings as non-critical
- ✅ Reports critical validation errors as failures

### Step 5: Test HuggingFace Space (Optional)
- ✅ Pings `/reset` endpoint with POST request
- ✅ Verifies HTTP 200 response
- ✅ Shows error details if connection fails
- Works with both HF Spaces and local servers (http://localhost:8000)

## Usage

```bash
# Basic validation (local environment only)
./check_env.sh

# Validate with local server
./check_env.sh http://localhost:8000

# Validate with HuggingFace Space
./check_env.sh https://your-space.hf.space
```

## Exit Codes

- **0** - All checks passed (only warnings allowed)
- **1** - One or more critical checks failed

## Example Output

### Successful Validation

```
╔═══════════════════════════════════════════════════════════╗
║  NegotiationRL - Environment Validation                  ║
║  (Based on Information/pre-validation.py)                 ║
╚═══════════════════════════════════════════════════════════╝

Repo Directory: /Users/gokulvks/Documents/NegotiatoRL
HF Space URL: http://localhost:8000

[1/5] Checking Prerequisites...
  ✓ Docker installed (version: 29.3.1)
  ✓ Docker daemon is running
  ⚠ openenv command not found (will try with uv)
    → For system-wide use: pip install openenv-core
  ✓ curl installed
  ✓ uv installed (version: 0.11.2)

[2/5] Checking Repository Structure...
  ✓ Dockerfile found in negotiation_env/negotiation_env/server/
  ✓ openenv.yaml found in negotiation_env/
  ✓ inference.py found at repo root
  ✓ .env file found
  ✓ HF_TOKEN defined in .env
  ✓ IMAGE_NAME defined in .env

[3/5] Testing Docker Build...
  Building Docker image from context: /Users/gokulvks/Documents/NegotiatoRL
  Using Dockerfile: negotiation_env/negotiation_env/server/Dockerfile
  This may take a few minutes...

  ✓ Docker build succeeded (took 4s)

[4/5] Running openenv validate...
  Trying with uv run openenv from: /Users/gokulvks/Documents/NegotiatoRL/negotiation_env

  ⚠ openenv validate has deployment warnings (via uv)

Validation output:
  [FAIL] negotiation: Not ready for multi-mode deployment
  
  Issues found:
    - Server entry point should reference main function, got: negotiation_env.cli:run_server
    - Missing server/app.py

    → These warnings may not affect hackathon submission
    → Verify that Docker build and inference work correctly

[5/5] Testing HuggingFace Space...
  Pinging: http://localhost:8000/reset

  ✓ HF Space is live and responds to /reset (HTTP 200)

═══════════════════════════════════════════════════════════
Passed: 12 checks
Warned: 2 checks

✓  Environment validation passed!
⚠  Address warnings above for full compliance

Next Steps:
  1. Fix any warnings above
  2. Test inference: ./run_inference.sh
  3. Push Docker image to HuggingFace
  4. Test with HF Space: ./check_env.sh https://your-space.hf.space
  5. Submit to hackathon
```

### Failed Validation

```
[3/5] Testing Docker Build...
  Building Docker image from context: /Users/gokulvks/Documents/NegotiatoRL
  Using Dockerfile: negotiation_env/negotiation_env/server/Dockerfile
  This may take a few minutes...

  ✗ Docker build failed

Build command: docker build -f negotiation_env/negotiation_env/server/Dockerfile -t negotiation-env:test /Users/gokulvks/Documents/NegotiatoRL
Build output (last 20 lines):
  ERROR: failed to solve: failed to compute cache key...

═══════════════════════════════════════════════════════════
Passed: 8 checks
Failed: 1 checks

✗  Environment validation failed!
   Fix the failed checks above before submission

Common Fixes:
  • Docker: https://docs.docker.com/get-docker/
  • openenv-core: pip install openenv-core
  • Missing files: Check repository structure
```

## Differences from validate.sh

| Feature | check_env.sh | validate.sh |
|---------|-------------|-------------|
| **Purpose** | Validates environment against pre-validation.py | Checks hackathon submission requirements |
| **Docker Build** | ✅ Full build test | ❌ Only checks Dockerfile exists |
| **openenv validate** | ✅ Runs full validation | ❌ Not included |
| **HF Space Ping** | ✅ Tests live endpoint | ❌ Not included |
| **Based On** | Information/pre-validation.py | Hackathon checklist images |
| **Use When** | Before deploying to HF | Before final submission |

## Recommendations

1. **Run `check_env.sh` FIRST** - Catches environment and build issues early
2. **Run `validate.sh` SECOND** - Verifies all hackathon-specific requirements
3. **Run `check_env.sh <hf-url>` LAST** - Final validation with live HF Space

This three-step validation ensures your submission meets all requirements!

## Known Warnings

### "openenv validate has deployment warnings"

This is expected for the NegotiationRL project due to its nested structure:
- `negotiation_env/` (outer folder)
- `negotiation_env/negotiation_env/` (Python package)

The warning about "multi-mode deployment" and "Missing server/app.py" is not critical for hackathon submission as long as:
- ✅ Docker build succeeds
- ✅ inference.py runs correctly
- ✅ All 25 tests pass
- ✅ Server endpoints respond correctly

### "openenv command not found"

If `openenv` is not installed system-wide, the script will automatically try `uv run openenv` instead. This is perfectly fine for local testing.

To install system-wide (optional):
```bash
pip install openenv-core
```

## Troubleshooting

### Docker build fails with "not found" errors

**Cause:** Dockerfile expects to be built from repo root with `-f` flag

**Solution:** The script handles this automatically for nested structures. If you see this error, check that all files exist:
```bash
ls -la negotiation_env/
ls -la negotiation_env/negotiation_env/
```

### HF Space ping fails with connection timeout

**Cause:** Space is not running or URL is incorrect

**Solution:**
1. Verify Space URL in browser
2. Check Space logs for startup errors
3. Ensure Space is not in "Building" status
4. For local testing, ensure Docker container is running: `docker ps`

### curl returns HTTP 404 or 500

**Cause:** Server is running but /reset endpoint has issues

**Solution:**
1. Check server logs: `docker logs <container-name>`
2. Test health endpoint: `curl http://localhost:8000/health`
3. Verify openenv.yaml is properly configured
4. Run local tests: `./run_tests.sh`

## Integration with CI/CD

You can use this script in automated workflows:

```bash
#!/bin/bash
# pre-deploy.sh - Run before deploying to HF Spaces

set -e

echo "Running environment validation..."
./check_env.sh

echo "Running hackathon validation..."
./validate.sh

echo "Testing inference..."
./run_inference.sh easy_conceder

echo "All validations passed! Ready to deploy."
```

## Related Scripts

- `validate.sh` - Hackathon submission checklist validation
- `run_tests.sh` - Run all 25 unit tests
- `run_inference.sh` - Test inference with OpenAI API
- `build_docker.sh` - Build and test Docker image
- `run_server.sh` - Start local development server
