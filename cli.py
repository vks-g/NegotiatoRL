"""
CLI entry points for development commands.

These functions are registered as console scripts in pyproject.toml,
allowing usage like: `uv run server` and `uv run test`
"""

import subprocess
import sys
from pathlib import Path


def run_server() -> None:
    """Start the uvicorn server with reload enabled for development."""
    # Get the root directory (where this file lives)
    root_dir = Path(__file__).parent

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "server.app:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]

    try:
        subprocess.run(cmd, cwd=root_dir, check=True)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


def run_tests() -> None:
    """Run pytest on the test suite with verbose output."""
    root_dir = Path(__file__).parent
    test_file = root_dir / "test_env.py"

    cmd = [sys.executable, "-m", "pytest", str(test_file), "-v"]

    # Pass through any additional arguments
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])

    try:
        result = subprocess.run(cmd, cwd=root_dir)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nTests interrupted.")
        sys.exit(1)


if __name__ == "__main__":
    # Default to running server if called directly
    run_server()
