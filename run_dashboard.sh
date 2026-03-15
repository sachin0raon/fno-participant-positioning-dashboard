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

cleanup() {
 echo -e "\n🛑 Stopping all services..."
 kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
 wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
 exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 Starting FastAPI backend on http://127.0.0.1:8000..."
./"$VENV_DIR"/bin/python -m uvicorn fno_dashboard:app --host 127.0.0.1 --port 8000 --reload --log-level info &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend..."
BACKEND_STARTED=false
for i in {1..3}; do
 if curl -s http://127.0.0.1:8000/api/health > /dev/null; then
  BACKEND_STARTED=true
  echo "✅ Backend is live!"
  break
 fi
 sleep 1
done

if [ "$BACKEND_STARTED" = false ]; then
 echo "❌ Backend failed to start. Exiting."
 kill $BACKEND_PID 2>/dev/null
 exit 1
fi

echo "🚀 Starting Vite dev server on http://localhost:5173..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✨ Dashboard fully operational!"
echo " Frontend: http://localhost:5173"
echo " Backend: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop."

# Wait for background processes and monitor for crashes
while true; do
 # Check if either process has died
 if ! kill -0 $BACKEND_PID 2>/dev/null; then
  echo "❌ Backend process died. Exiting."
  kill $FRONTEND_PID 2>/dev/null
  exit 1
 fi

 if ! kill -0 $FRONTEND_PID 2>/dev/null; then
  echo "❌ Frontend process died. Exiting."
  kill $BACKEND_PID 2>/dev/null
  exit 1
 fi

 wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
 EXIT_CODE=$?

 # If wait returns (process exited), check exit code
 if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ A process exited with code $EXIT_CODE. Exiting."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 1
 fi
done