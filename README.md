# 💰 Budget Tracker Hybrid (FastAPI + aiogram + SQLite)

A lightweight, hybrid personal finance management tool running as a single-process FastAPI REST backend, live Web Dashboard, and Telegram Bot simultaneously with minimal RAM footprint (<150MB RSS).

---

## ✨ Features

- **⚡ Ultra-Low Memory Footprint**: Optimized single-process architecture using asynchronous background polling. Typically uses **~15–20MB RSS** under load.
- **🤖 Telegram Bot Integration**: Powered by `aiogram` 3.x. Manage your finances right from your Telegram chat.
  - `/start` — interactive welcome menu
  - `/stats` — current monthly income, expense & balance
  - `/categories` — list active budget categories
  - `/add_expense <amount> <category> [description]`
  - `/add_income <amount> <category> [description]`
- **🌐 Responsive Web Dashboard**: Dark-themed, zero-framework, single-page UI served directly from the root path (`/`). Real-time auto-refresh, quick transaction entry, and tabular history.
- **🔌 RESTful API**: Built with FastAPI. Interactive Swagger UI docs available at `/docs` and ReDoc at `/redoc`.
- **🗄️ SQLite Storage**: Zero-config persistent relational database with automatic tables and sample category provisioning.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (Recommended: Python 3.12)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Clone & Setup
```bash
git clone https://github.com/bahalil71/budget-tracker.git
cd budget-tracker

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install fastapi "uvicorn[standard]" aiogram sqlalchemy pydantic-settings python-multipart
```

### 3. Environment Configuration
Create a `.env` file in the project root:
```env
BOT_TOKEN=your_telegram_bot_token_here
```

### 4. Run Application
Run both the Web Dashboard, REST API, and Telegram Bot polling concurrently:
```bash
PYTHONOPTIMIZE=2 python main.py
```

The application will start on port `8088`:
- **Web Dashboard**: `http://localhost:8088/`
- **Swagger Docs**: `http://localhost:8088/docs`
- **Health Check**: `http://localhost:8088/health`

---

## 🛠️ Architecture

```
                 +-----------------------+
                 |     Telegram User     |
                 +-----------+-----------+
                             |
                       aiogram (Long Poll)
                             |
+----------------------------v----------------------------+
|                    budget-tracker                       |
|                                                         |
|   +-------------------+         +-------------------+   |
|   |   FastAPI REST    | <-----> |   SQLite Engine   |   |
|   |   & Static Web    |         |    (budget.db)    |   |
|   +---------^---------+         +-------------------+   |
|             |                                           |
+-------------+-------------------------------------------+
              |
        HTTP / JSON
              |
    +---------v---------+
    |   Web Dashboard   |
    |  (Browser Client) |
    +-------------------+
```

---

## 🔒 Security & Privacy
- Sensitive files (`.env`, `budget.db`, logs) are excluded by `.gitignore`.
- SQLite database stays on-premise / local storage with zero third-party telemetry.

---

## 📄 License
MIT License. Free for personal and commercial usage.
