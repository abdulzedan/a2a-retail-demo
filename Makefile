# A2A Retail Demo Makefile
.PHONY: help setup install clean test check start stop dev

# Default target
help:
	@echo "🚀 A2A Retail Demo - Available Commands"
	@echo "======================================"
	@echo "setup     - Set up development environment"
	@echo "install   - Install dependencies"  
	@echo "check     - Check system requirements and configuration"
	@echo "test      - Run tests"
	@echo "clean     - Clean up generated files"
	@echo "start     - Start all A2A agents and frontend"
	@echo "stop      - Stop all running services"
	@echo "help      - Show this help message"

# Set up development environment
setup:
	@echo "🛠️  Setting up development environment..."
	python3 -m venv .venv || python -m venv .venv
	@echo "📦 Installing dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@echo "✅ Setup complete! Don't forget to:"
	@echo "   1. Copy .env.example to .env"
	@echo "   2. Set your GOOGLE_API_KEY in .env"

# Install dependencies only
install:
	@echo "📦 Installing dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

# Start all services
start:
	@echo "🚀 Starting A2A Retail Demo..."
	chmod +x scripts/start_a2a_demo.sh
	./scripts/start_a2a_demo.sh

# Stop all services  
stop:
	@echo "🛑 Stopping all services..."
	-pkill -f "inventory_agent_a2a"
	-pkill -f "customer_service_a2a"
	-pkill -f "frontend/app.py"
	@echo "✅ All services stopped"

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Development mode (same as start)
dev: start

# Check system
check:
	@echo "🔍 Checking system requirements..."
	@python --version
	@echo "📦 Checking dependencies..."
	@.venv/bin/pip list | grep -E "(google-adk|langchain|mesop|a2a)" || echo "⚠️  Some dependencies missing"