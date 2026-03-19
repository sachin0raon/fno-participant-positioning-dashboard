# 📊 F&O Participant Positioning Dashboard

> **A high-performance, real-time analytics dashboard for NSE India Futures & Options participant positioning.**

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

---

## ✨ Overview

The **F&O Dashboard** provides advanced insights into how different market participants (FII, DII, PRO, and RETAIL) are positioned in the Indian derivatives market. It fetches live data from the **National Stock Exchange (NSE)**, analyzes net changes in Open Interest across Futures, Calls, and Puts, and presents them through a premium, glassmorphic interface.

### 🌟 Key Features

- **🚀 Real-time NSE Data**: Fetches and parses participant-wise OI data directly from NSE India using `nselib`.
- **📈 Advanced Sentiment Analysis**: Proprietary logic to calculate sentiment scores and market direction for each participant category.
- **📱 Telegram Integration**: Automated delivery of daily EOD reports and interactive commands (`/recent`, `/date`, `/cron`). The `/recent` command intelligently fetches today's data or falls back to the latest available trading day.
- **💎 Premium UI**: Built with React 19, Framer Motion for smooth animations, and Tailwind CSS 4 for a modern "Glassmorphism" aesthetic.
- **🐳 Containerized**: Fully Dockerized for seamless deployment across any environment.
- **📅 Historical Look-back**: Easily navigate and compare positioning across the last 30 trading days.

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.12+)
- **Data Source**: `nselib` (NSE India Derivatives API)
- **Task Runner**: APScheduler for automated reports.
- **Bot logic**: `python-telegram-bot` for interactive messaging.

### Frontend
- **Framework**: React 19 (Vite)
- **Styling**: Tailwind CSS 4 & Radix UI (Headless components).
- **Animations**: Framer Motion.
- **Icons**: Lucide React.
- **State Management**: TanStack Query (v5) for efficient caching.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 20+
- Bash environment (for the start script)

### 2. Run with One Command
Use the provided automation script to set up virtual environments, install dependencies, and launch both services:

```bash
chmod +x run_dashboard.sh
./run_dashboard.sh
```

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚙️ Manual Setup

### Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn fno_dashboard:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 🏗️ Docker Deployment

Deploy the entire stack in seconds using the optimized multi-stage `Dockerfile`:

```bash
# Build the image
docker build -t fno-dashboard .

# Run the container
docker run -p 8000:8000 --env-file .env fno-dashboard
```

---

## 🌐 Environment Variables

Create a `.env` file in the root directory:

```env
# Telegram Configuration (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_CRON_SCHEDULE="0 16 * * 1-5"  # 4 PM on Weekdays

# API Configuration
PORT=8000
HOST=0.0.0.0
```

---

## 📸 Preview

*Add your screenshots here! The dashboard features a stunning Bento-grid layout with dynamic sentiment indicators.*

---

## 📄 License

This project is for educational and personal use only. Market data is sourced from NSE India.

Created with ❤️ by **Antigravity** (Senior Frontend Design Engineer)
