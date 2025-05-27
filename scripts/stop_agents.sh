#!/usr/bin/env bash
#
# scripts/stop_agents.sh
# Stop all A2A Retail Demo services
# -----------------------------------------------------------------------------

echo "🛑 Stopping A2A Retail Demo services..."

# Kill processes by name (more comprehensive)
pkill -f "run_inventory_agent.py" 2>/dev/null && echo "✅ Stopped Inventory Agent" || echo "⚠️  Inventory Agent process not found"
pkill -f "run_customer_service_agent.py" 2>/dev/null && echo "✅ Stopped Customer Service Agent" || echo "⚠️  Customer Service Agent process not found" 
pkill -f "run_mesop_app.py" 2>/dev/null && echo "✅ Stopped Mesop UI" || echo "⚠️  Mesop UI process not found"
pkill -f "frontend/app.py" 2>/dev/null && echo "✅ Stopped Mesop UI (alternative)" || true

# Kill any Python processes on our ports
echo "🔍 Checking for processes on ports 8000, 8001, 8002..."

for port in 8000 8001 8002; do
  pids=$(lsof -ti:$port 2>/dev/null)
  if [[ -n "$pids" ]]; then
    echo "🔧 Killing processes on port $port: $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    echo "✅ Freed port $port"
  else
    echo "✓ Port $port is free"
  fi
done

# Kill any remaining uvicorn processes
pkill -f "uvicorn" 2>/dev/null && echo "✅ Stopped uvicorn processes" || true

# Kill any remaining Python processes that might be our agents
ps aux | grep -E "(inventory_agent|customer_service|mesop)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true

sleep 2

echo "🏁 All services stopped!"
echo
echo "🔍 Port status:"
for port in 8000 8001 8002; do
  if lsof -ti:$port >/dev/null 2>&1; then
    echo "❌ Port $port still in use"
  else
    echo "✅ Port $port is free"
  fi
done