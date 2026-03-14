#!/bin/bash
# Run the F&O Dashboard (Backend + Frontend)

echo "=== F&O Positioning Dashboard ==="
echo ""

# Load NVM for Node.js support
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
fi

# ─── Python Environment ───
VENV_DIR=".venv"

echo "🐍 Checking Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Ensure Python dependencies are met
echo "📦 Installing Python dependencies from requirements.txt..."
./"$VENV_DIR"/bin/pip install -r requirements.txt > /dev/null 2>&1

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# ─── Process Management ───

# Trap SIGINT (Ctrl+C) and SIGTERM
# 'kill 0' sends the signal to all processes in the current process group
trap "echo -e '\n🛑 Stopping all services...'; kill 0" SIGINT SIGTERM

echo "🚀 Starting FastAPI backend on http://127.0.0.1:8000..."
# Running uvicorn via venv python
./"$VENV_DIR"/bin/python -m uvicorn fno_dashboard:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:8000/api/health > /dev/null; then
        echo "✅ Backend is live!"
        break
    fi
    sleep 1
done

echo "🚀 Starting Vite dev server on http://localhost:5173..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✨ Dashboard fully operational!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop."

# Wait for background processes
wait
