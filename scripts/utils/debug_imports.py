#!/usr/bin/env python3
"""Debug script to test all imports and components."""

import sys
import os
from pathlib import Path

# Add project root to Python path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print(f"🔍 Debug Information")
print(f"📁 Working directory: {os.getcwd()}")
print(f"📁 Script location: {ROOT}")
print(f"🐍 Python version: {sys.version}")
print(f"🐍 Python path (first 3): {sys.path[:3]}")
print()

# Test imports one by one
print("🧪 Testing imports...")

try:
    import mesop as me
    print("✅ mesop imported successfully")
except ImportError as e:
    print(f"❌ Failed to import mesop: {e}")
    sys.exit(1)

try:
    import structlog
    print("✅ structlog imported successfully")
except ImportError as e:
    print(f"❌ Failed to import structlog: {e}")

try:
    from backend.config import settings
    print("✅ backend.config imported successfully")
    print(f"   📊 Settings available: {type(settings)}")
except ImportError as e:
    print(f"❌ Failed to import backend.config: {e}")
    print("   Check if backend/config/settings.py exists")

try:
    from backend.a2a import A2AClient
    print("✅ backend.a2a imported successfully")
except ImportError as e:
    print(f"❌ Failed to import backend.a2a: {e}")
    print("   Check if backend/a2a/__init__.py exists")

try:
    from frontend.components import agent_status
    print("✅ frontend.components imported successfully")
except ImportError as e:
    print(f"❌ Failed to import frontend.components: {e}")
    print("   Check if frontend/components/__init__.py exists")

print()
print("🧪 Testing Mesop functionality...")

try:
    @me.page(path="/debug", title="Debug Page")
    def debug_page():
        me.text("Debug page works!")
    
    print("✅ Mesop page decorator works")
except Exception as e:
    print(f"❌ Mesop page decorator failed: {e}")

try:
    wsgi_app = me.create_wsgi_app()
    print("✅ Mesop WSGI app creation works")
except Exception as e:
    print(f"❌ Mesop WSGI app creation failed: {e}")

print()
print("🎉 Import debugging completed!")