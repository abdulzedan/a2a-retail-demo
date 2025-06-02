#!/usr/bin/env python3
"""
Test runner script for A2A retail demo.
"""
import sys
import subprocess
from pathlib import Path


def run_tests():
    """Run the test suite with various options."""

    # Get the project root
    project_root = Path(__file__).parent.parent.parent

    # Basic test command
    base_cmd = [sys.executable, "-m", "pytest"]

    # Different test configurations
    test_configs = {
        "all": ["--verbose"],
        "unit": ["-m", "unit", "--verbose"],
        "integration": ["-m", "integration", "--verbose"],
        "coverage": ["--cov=backend", "--cov-report=html", "--cov-report=term"],
        "fast": ["-x", "--tb=short"],  # Stop on first failure, short traceback
    }

    # Check command line arguments
    if len(sys.argv) > 1:
        config_name = sys.argv[1]
        if config_name in test_configs:
            cmd = base_cmd + test_configs[config_name]
        else:
            print(f"Unknown test configuration: {config_name}")
            print(f"Available options: {', '.join(test_configs.keys())}")
            return 1
    else:
        # Default: run all tests
        cmd = base_cmd + test_configs["all"]

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    # Run the tests
    result = subprocess.run(cmd, cwd=project_root)

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
