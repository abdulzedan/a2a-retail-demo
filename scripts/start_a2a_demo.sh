#!/usr/bin/env bash
#
# scripts/start_a2a_demo.sh  
# Start the A2A Retail Demo with proper A2A protocol
# ─────────────────────────────────────────────────────────────────────────────

set -Eeuo pipefail

# ── Locate project root & venv ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "❌ Virtual environment not found at ${VENV_DIR}/bin/python"
    echo "   Please run: make setup"
    exit 1
fi

# ── Load environment variables ──────────────────────────────────────────────
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    echo "📋 Loading environment variables..."
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
else
    echo "⚠️  No .env file found. Using defaults."
fi

# ── Configuration ───────────────────────────────────────────────────────────
INVENTORY_PORT="${INVENTORY_AGENT_PORT:-8001}"
CUSTOMER_SERVICE_PORT="${CUSTOMER_SERVICE_AGENT_PORT:-8002}"
HOST_PORT="${HOST_AGENT_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"

echo "🔧 Configuration:"
echo "   Inventory Agent: http://localhost:${INVENTORY_PORT}"
echo "   Customer Service: http://localhost:${CUSTOMER_SERVICE_PORT}"
echo "   Host Agent: http://localhost:${HOST_PORT}"
echo "   Frontend: http://localhost:${FRONTEND_PORT}"
echo

# ── Cleanup function ────────────────────────────────────────────────────────
cleanup() {
    echo
    echo "🛑 Stopping all A2A agents..."
    
    # Kill by process name
    pkill -f "inventory_agent_a2a.server" 2>/dev/null || true
    pkill -f "customer_service_a2a.server" 2>/dev/null || true
    pkill -f "host_agent.server" 2>/dev/null || true
    pkill -f "frontend/app.py" 2>/dev/null || true
    
    # Kill by port
    for port in $INVENTORY_PORT $CUSTOMER_SERVICE_PORT $HOST_PORT $FRONTEND_PORT; do
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
    done
    
    echo "✅ All services stopped"
    exit 0
}

trap cleanup EXIT INT TERM

# ── Check API key ───────────────────────────────────────────────────────────
if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
    echo "❌ GOOGLE_API_KEY is not set in .env file"
    echo "   Please set your Google API key in .env"
    exit 1
fi

# ── Install A2A SDK if not present ─────────────────────────────────────────
echo "🔍 Checking A2A SDK installation..."
if ! "${VENV_DIR}/bin/python" -c "import a2a" 2>/dev/null; then
    echo "📦 Installing A2A SDK..."
    "${VENV_DIR}/bin/pip" install a2a-sdk
fi

# ── Start agents ────────────────────────────────────────────────────────────
cd "${PROJECT_ROOT}"

echo "🚀 Starting A2A Retail Demo agents..."
echo

# Start inventory agent
echo "📦 Starting Inventory Agent on port ${INVENTORY_PORT}..."
"${VENV_DIR}/bin/python" -m backend.agents.inventory_agent_a2a.server --port $INVENTORY_PORT &
INVENTORY_PID=$!
sleep 3

# Start customer service agent  
echo "🎧 Starting Customer Service Agent on port ${CUSTOMER_SERVICE_PORT}..."
"${VENV_DIR}/bin/python" -m backend.agents.customer_service_a2a.server --port $CUSTOMER_SERVICE_PORT &
CUSTOMER_SERVICE_PID=$!
sleep 3

# Start host agent
echo "🏠 Starting Host Agent on port ${HOST_PORT}..."
"${VENV_DIR}/bin/python" -m backend.agents.host_agent.server --port $HOST_PORT &
HOST_PID=$!
sleep 3

# Start frontend
echo "🖥️  Starting Frontend on port ${FRONTEND_PORT}..."
MESOP_HOST=127.0.0.1 MESOP_PORT=$FRONTEND_PORT "${VENV_DIR}/bin/python" frontend/app.py &
FRONTEND_PID=$!
sleep 2

# ── Wait for services to be ready ──────────────────────────────────────────
echo "⏳ Waiting for services to be ready..."

check_service() {
    local url="$1"
    local name="$2"
    local max_attempts=15
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo "✅ $name is ready"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "⚠️  $name may not be ready (no response from $url)"
    return 1
}

# Check each agent
check_service "http://localhost:${INVENTORY_PORT}/.well-known/agent.json" "Inventory Agent"
check_service "http://localhost:${CUSTOMER_SERVICE_PORT}/.well-known/agent.json" "Customer Service Agent"  
check_service "http://localhost:${HOST_PORT}/.well-known/agent.json" "Host Agent"
check_service "http://localhost:${FRONTEND_PORT}" "Frontend"

# ── Test A2A protocol compliance ────────────────────────────────────────────
echo
echo "🧪 Testing A2A protocol compliance..."

# Test agent card endpoint
test_agent_card() {
    local url="$1"
    local name="$2"
    
    response=$(curl -s "$url/.well-known/agent.json")
    if echo "$response" | grep -q '"name"'; then
        echo "✅ $name agent card is valid"
    else
        echo "❌ $name agent card is invalid"
    fi
}

test_agent_card "http://localhost:${INVENTORY_PORT}" "Inventory"
test_agent_card "http://localhost:${CUSTOMER_SERVICE_PORT}" "Customer Service"
test_agent_card "http://localhost:${HOST_PORT}" "Host"

# ── Success banner ──────────────────────────────────────────────────────────
echo
echo "🎉 A2A Retail Demo is running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Frontend:          http://localhost:${FRONTEND_PORT}"
echo "  Host Agent:        http://localhost:${HOST_PORT}" 
echo "  Inventory Agent:   http://localhost:${INVENTORY_PORT}"
echo "  Customer Service:  http://localhost:${CUSTOMER_SERVICE_PORT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "🔗 A2A Protocol Endpoints:"
echo "   Agent Cards:     http://localhost:{PORT}/.well-known/agent.json"
echo "   JSON-RPC:        http://localhost:{PORT}/ (POST)"
echo
echo "💡 Try these queries in the frontend:"
echo "   • 'Do you have Smart TVs in stock?'"
echo "   • 'What's the status of order ORD-12345?'"
echo "   • 'Show me products under \$50'"
echo "   • 'What are your store hours?'"
echo
echo "📚 A2A Protocol Features:"
echo "   ✓ Proper task lifecycle management"
echo "   ✓ Context propagation across agents"
echo "   ✓ Streaming support (SSE)"
echo "   ✓ Standard A2A error handling"
echo
echo "Press Ctrl+C to stop all services"

# ── Wait for shutdown ───────────────────────────────────────────────────────
wait