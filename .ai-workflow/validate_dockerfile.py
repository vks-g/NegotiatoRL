#!/usr/bin/env python3
"""
Dockerfile Validation Script

Validates the Dockerfile structure and configuration without requiring Docker.
Checks syntax, paths, and compliance with OpenEnv patterns.
"""

import re
from pathlib import Path


def validate_dockerfile():
    """Validate Dockerfile configuration."""

    repo_root = Path(__file__).parent.parent
    dockerfile_path = repo_root / "negotiation_env" / "server" / "Dockerfile"

    print("=" * 70)
    print("DOCKERFILE VALIDATION")
    print("=" * 70)

    # Check file exists
    if not dockerfile_path.exists():
        print("❌ FAIL: Dockerfile not found at expected path")
        return False

    print(f"✅ Found Dockerfile at: {dockerfile_path}")

    # Read content
    content = dockerfile_path.read_text()

    checks = []

    # Check 1: Quoted version specifiers
    print("\n1. Checking pip version specifiers...")
    unquoted_pattern = r'pip install.*?(\w+>=[\d.]+)(?!["\'])'
    unquoted_matches = re.findall(unquoted_pattern, content)

    if unquoted_matches:
        print(f"   ❌ FAIL: Found unquoted version specifiers: {unquoted_matches}")
        checks.append(False)
    else:
        quoted_pattern = r'"[^"]+>=[\d.]+"'
        quoted_matches = re.findall(quoted_pattern, content)
        print(
            f"   ✅ PASS: All version specifiers quoted ({len(quoted_matches)} found)"
        )
        checks.append(True)

    # Check 2: Correct CMD module path
    print("\n2. Checking uvicorn module path...")
    cmd_pattern = r"uvicorn\s+(\S+):app"
    cmd_matches = re.findall(cmd_pattern, content)

    if not cmd_matches:
        print("   ❌ FAIL: No uvicorn command found")
        checks.append(False)
    elif "negotiation_env.server.app" not in cmd_matches[0]:
        print(f"   ❌ FAIL: Incorrect module path: {cmd_matches[0]}")
        print(f"   Expected: negotiation_env.server.app")
        checks.append(False)
    else:
        print(f"   ✅ PASS: Correct module path: {cmd_matches[0]}")
        checks.append(True)

    # Check 3: Build context documentation
    print("\n3. Checking build context documentation...")
    if "negotiation_env/server/Dockerfile" in content:
        print("   ✅ PASS: Correct Dockerfile path in comments")
        checks.append(True)
    else:
        print("   ❌ FAIL: Incorrect Dockerfile path in comments")
        checks.append(False)

    # Check 4: COPY commands use correct paths
    print("\n4. Checking COPY commands...")
    copy_pattern = r"COPY\s+(\S+)\s+(\S+)"
    copy_matches = re.findall(copy_pattern, content)

    valid_copies = True
    for src, dst in copy_matches:
        if src.startswith("negotiation_env"):
            print(f"   ✅ PASS: COPY {src} {dst}")
        elif src in [".", ".."]:
            print(f"   ⚠️  WARNING: COPY {src} {dst} (might include unnecessary files)")
        else:
            print(f"   ❌ FAIL: COPY {src} {dst} (incorrect source path)")
            valid_copies = False

    checks.append(valid_copies)

    # Check 5: PYTHONPATH set correctly
    print("\n5. Checking PYTHONPATH...")
    if 'ENV PYTHONPATH="/app:' in content:
        print("   ✅ PASS: PYTHONPATH includes /app")
        checks.append(True)
    else:
        print("   ❌ FAIL: PYTHONPATH not set correctly")
        checks.append(False)

    # Check 6: Health check present
    print("\n6. Checking health check...")
    if "HEALTHCHECK" in content and "/health" in content:
        print("   ✅ PASS: Health check configured")
        checks.append(True)
    else:
        print("   ❌ FAIL: Health check missing or incorrect")
        checks.append(False)

    # Check 7: Environment variables
    print("\n7. Checking environment variables...")
    required_envs = ["HOST", "PORT", "WORKERS"]
    for env_var in required_envs:
        if f"ENV {env_var}=" in content:
            print(f"   ✅ PASS: {env_var} defined")
        else:
            print(f"   ❌ FAIL: {env_var} not defined")
            checks.append(False)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(checks)
    total = len(checks)

    print(f"\nPassed: {passed}/{total} checks")

    if all(checks):
        print("\n✅ ALL CHECKS PASSED - Dockerfile is ready for testing")
        return True
    else:
        print("\n❌ SOME CHECKS FAILED - Review issues above")
        return False


def validate_structure():
    """Validate project structure."""

    repo_root = Path(__file__).parent.parent

    print("\n" + "=" * 70)
    print("PROJECT STRUCTURE VALIDATION")
    print("=" * 70)

    required_files = [
        "negotiation_env/__init__.py",
        "negotiation_env/models.py",
        "negotiation_env/client.py",
        "negotiation_env/server/app.py",
        "negotiation_env/server/environment.py",
        "negotiation_env/server/Dockerfile",
        "negotiation_env/pyproject.toml",
        ".dockerignore",
    ]

    all_exist = True

    for file_path in required_files:
        full_path = repo_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            all_exist = False

    return all_exist


def print_commands():
    """Print exact commands for testing."""

    print("\n" + "=" * 70)
    print("DOCKER COMMANDS FOR TESTING")
    print("=" * 70)

    print("\n1. Build (from repository root):")
    print(
        "   docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile ."
    )

    print("\n2. Run (basic):")
    print(
        "   docker run -d -p 8000:8000 --name test-negotiation-env negotiation-env:latest"
    )

    print("\n3. Health check:")
    print("   curl http://localhost:8000/health")

    print("\n4. Test import:")
    print(
        "   docker exec -it test-negotiation-env python -c \"from negotiation_env.server.app import app; print('✓ Success')\""
    )

    print("\n5. Cleanup:")
    print("   docker stop test-negotiation-env && docker rm test-negotiation-env")

    print("\n" + "=" * 70)
    print("UV COMMANDS (Alternative to Docker)")
    print("=" * 70)

    print("\n1. Sync dependencies:")
    print("   cd negotiation_env && uv sync")

    print("\n2. Run server:")
    print("   uv run server")

    print("\n3. Test (in another terminal):")
    print("   curl http://localhost:8000/health")


if __name__ == "__main__":
    dockerfile_valid = validate_dockerfile()
    structure_valid = validate_structure()

    print_commands()

    print("\n" + "=" * 70)
    print("FINAL STATUS")
    print("=" * 70)

    if dockerfile_valid and structure_valid:
        print("\n✅ ✅ ✅  ALL VALIDATIONS PASSED  ✅ ✅ ✅")
        print("\nThe Dockerfile is ready for Docker build testing.")
        print("Run the commands above to verify the container works.")
        exit(0)
    else:
        print("\n❌ ❌ ❌  VALIDATION FAILED  ❌ ❌ ❌")
        print("\nReview the issues above and fix before building.")
        exit(1)
