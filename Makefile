# A2A Retail Demo Makefile
.PHONY: help setup install install-dev clean test test-unit test-integration test-coverage lint format check check-setup start stop dev start-host start-inventory start-customer-service start-frontend test-a2a quickstart

# Default target
help:
	@echo "🚀 A2A Retail Demo - Available Commands"
	@echo "======================================"
	@echo "setup     - Set up development environment (venv + deps)"
	@echo "install   - Install production dependencies"
	@echo "install-dev - Install development dependencies"  
	@echo "check     - Check system requirements"
	@echo "check-setup - Run comprehensive setup verification"
	@echo "test      - Run all tests"
	@echo "test-unit - Run unit tests only"
	@echo "test-integration - Run integration tests only"
	@echo "test-coverage - Run tests with coverage report"
	@echo "test-a2a  - Test A2A agent communication"
	@echo "lint      - Run code linting"
	@echo "format    - Format code with black and ruff"
	@echo "clean     - Clean up generated files"
	@echo ""
	@echo "🚀 Running Services:"
	@echo "start     - Start all A2A agents and frontend"
	@echo "stop      - Stop all running services"
	@echo "start-host - Start only the host agent (port 8000)"
	@echo "start-inventory - Start only inventory agent (port 8001)"
	@echo "start-customer-service - Start only customer service agent (port 8002)"
	@echo "start-frontend - Start only the frontend (port 5000)"
	@echo "quickstart - Quick setup check and start all services"
	@echo ""
	@echo "help      - Show this help message"

# Set up development environment
setup:
	@echo "🛠️  Setting up development environment..."
	python3 -m venv .venv || python -m venv .venv
	@echo "📦 Installing all dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -r requirements-dev.txt
	@echo "📋 Setting up environment variables..."
	@if [ ! -f .env ]; then cp .env.example .env && echo "   ✅ Created .env from .env.example"; else echo "   ℹ️  .env already exists"; fi
	@echo ""
	@echo "✅ Setup complete! Next steps:"
	@echo "   1. Set your GOOGLE_API_KEY in .env"
	@echo "   2. Configure VERTEX_SEARCH_SERVING_CONFIG in .env"
	@echo "   3. Run 'make check-setup' to verify installation"

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

# Run all tests
test:
	@echo "🧪 Running all tests..."
	.venv/bin/python -m pytest backend/tests -v

# Run unit tests only
test-unit:
	@echo "🧪 Running unit tests..."
	.venv/bin/python -m pytest backend/tests -v -m "not integration"

# Run integration tests only  
test-integration:
	@echo "🧪 Running integration tests..."
	.venv/bin/python -m pytest backend/tests -v -m integration

# Run tests with coverage
test-coverage:
	@echo "📊 Running tests with coverage..."
	.venv/bin/python -m pytest backend/tests --cov=backend --cov-report=html --cov-report=term

# Run linting
lint:
	@echo "🔍 Running linter..."
	.venv/bin/ruff check .

# Install development dependencies
install-dev:
	@echo "📦 Installing development dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements-dev.txt

# Format code
format:
	@echo "🎨 Formatting code with black and ruff..."
	.venv/bin/black backend/
	.venv/bin/ruff check . --fix

# Check system
check:
	@echo "🔍 Checking system requirements..."
	@python --version
	@echo "📦 Checking key dependencies..."
	@.venv/bin/pip list | grep -E "(google-adk|langchain|mesop|a2a)" || echo "⚠️  Some dependencies missing"

# Comprehensive setup check
check-setup:
	@echo "🔍 Running comprehensive setup verification..."
	.venv/bin/python scripts/dev_utils.py --check

# Test A2A agent communication
test-a2a:
	@echo "🧪 Testing A2A agent setup and communication..."
	.venv/bin/python scripts/test_a2a_setup.py

# Start individual agents
start-host:
	@echo "🏠 Starting Host Agent on port 8000..."
	.venv/bin/python -m backend.agents.host_agent.server

start-inventory:
	@echo "📦 Starting Inventory Agent on port 8001..."
	.venv/bin/python -m backend.agents.inventory_agent_a2a.server

start-customer-service:
	@echo "🎧 Starting Customer Service Agent on port 8002..."
	.venv/bin/python -m backend.agents.customer_service_a2a.server

# Start frontend only
start-frontend:
	@echo "🖥️  Starting Frontend on port 5000..."
	MESOP_HOST=127.0.0.1 MESOP_PORT=5000 .venv/bin/python frontend/app.py

# Quick start - minimal setup check and run
quickstart: check start
	@echo "🚀 A2A Retail Demo is running!"