# 🌐 Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy frontend source
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# 🐍 Stage 2: Final Image
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY fno_dashboard.py .

# Copy built frontend from Stage 1 to a 'dist' directory (matching fno_dashboard.py expectation)
COPY --from=frontend-builder /app/frontend/dist ./dist

# Expose port
EXPOSE 8000

# Set production environment
ENV PYTHONUNBUFFERED=1

# Run the backend using uvicorn module (bind to 0.0.0.0 for Docker)
CMD ["python", "-m", "uvicorn", "fno_dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
