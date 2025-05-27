#!/usr/bin/env python3
"""Development utilities for A2A Retail Demo."""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_python_version():
    """Check Python version requirements."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("❌ Python 3.11+ required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_virtual_environment():
    """Check if virtual environment exists."""
    venv_path = ROOT / ".venv"
    if venv_path.exists():
        print("✅ Virtual environment found")
        return True
    print("❌ Virtual environment not found")
    return False


def check_environment_file():
    """Check if .env file exists and has required variables."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        print("❌ .env file not found")
        return False
    
    # Check for required variables
    required_vars = ["GOOGLE_API_KEY"]
    missing_vars = []
    
    with open(env_path) as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" not in content or f"{var}=your-" in content:
                missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ Environment file configured")
    return True


def check_dependencies():
    """Check if dependencies are installed."""
    try:
        import google.adk
        import langchain
        import mesop
        import a2a
        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        return False


def check_ports():
    """Check if required ports are available."""
    import socket
    
    ports = [8000, 8001, 8002, 8080]
    busy_ports = []
    
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                busy_ports.append(port)
    
    if busy_ports:
        print(f"⚠️  Ports in use: {', '.join(map(str, busy_ports))}")
        print("   You may need to stop other services")
        return False
    
    print("✅ Required ports available")
    return True


def setup_project():
    """Set up the project structure."""
    print("🛠️  Setting up project structure...")
    
    # Create directories
    directories = [
        "backend/agents/inventory_agent_a2a",
        "backend/agents/customer_service_a2a",
        "backend/host_agent",
        "backend/utils",
        "scripts",
        "logs",
        "data",
    ]
    
    for directory in directories:
        dir_path = ROOT / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"   Created: {directory}")
    
    # Create __init__.py files
    init_files = [
        "backend/__init__.py",
        "backend/agents/__init__.py",
        "backend/agents/inventory_agent_a2a/__init__.py",
        "backend/agents/customer_service_a2a/__init__.py",
        "backend/host_agent/__init__.py",
        "backend/utils/__init__.py",
    ]
    
    for init_file in init_files:
        file_path = ROOT / init_file
        if not file_path.exists():
            file_path.touch()
            print(f"   Created: {init_file}")
    
    print("✅ Project structure ready")


def clean_project():
    """Clean up generated files."""
    print("🧹 Cleaning up project...")
    
    # Remove Python cache
    import shutil
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    for pyc_file in ROOT.rglob("*.pyc"):
        pyc_file.unlink(missing_ok=True)
    
    # Clean logs
    logs_dir = ROOT / "logs"
    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            log_file.unlink(missing_ok=True)
    
    print("✅ Project cleaned")


def test_setup():
    """Test the setup."""
    print("🧪 Testing setup...")
    
    # Run the test script
    test_script = ROOT / "scripts" / "test_a2a_setup.py"
    if test_script.exists():
        try:
            result = subprocess.run([
                sys.executable, str(test_script)
            ], capture_output=True, text=True, cwd=ROOT)
            
            if result.returncode == 0:
                print("✅ Setup test passed")
                return True
            else:
                print("❌ Setup test failed")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            return False
    else:
        print("⚠️  Test script not found")
        return False


def main():
    """Main entry point for dev utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description="A2A Retail Demo Development Utilities")
    parser.add_argument("--check", action="store_true", help="Check system requirements")
    parser.add_argument("--setup", action="store_true", help="Set up project structure")
    parser.add_argument("--clean", action="store_true", help="Clean up generated files")
    parser.add_argument("--test", action="store_true", help="Test the setup")
    
    args = parser.parse_args()
    
    if args.check:
        print("🔍 Checking system requirements...")
        checks = [
            ("Python version", check_python_version),
            ("Virtual environment", check_virtual_environment),
            ("Environment file", check_environment_file),
            ("Dependencies", check_dependencies),
            ("Ports", check_ports),
        ]
        
        all_passed = True
        for name, check_func in checks:
            print(f"\n{name}:")
            if not check_func():
                all_passed = False
        
        if all_passed:
            print("\n🎉 All checks passed!")
        else:
            print("\n❌ Some checks failed. Please fix the issues above.")
            sys.exit(1)
    
    elif args.setup:
        setup_project()
    
    elif args.clean:
        clean_project()
    
    elif args.test:
        if not test_setup():
            sys.exit(1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()