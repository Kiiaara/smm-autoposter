# 📱 SMM Autoposter

Full-stack social media automation platform: schedule and auto-post content to Telegram, VK, Instagram, and more.

**Key Features:**
- 📅 Content scheduling with calendar UI
- 🎨 Media upload (images, videos with thumbnails)
- 🔄 Multi-platform publishing (Telegram, VK, Instagram)
- 📊 Analytics dashboard
- ⚙️ Channel management & configuration
- 🎯 Recurring schedule support

---

## 🏗️ Tech Stack

- **Backend:** FastAPI (Python 3.9+)
- **Frontend:** React 18 + Vite
- **Database:** SQLite (local) / PostgreSQL (production)
- **Scheduler:** APScheduler (checks every 60s)
- **Media:** Image resize, thumbnail generation

---

## 🚀 Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup config
cp .env.example .env
# Edit .env with API tokens:
# - TELEGRAM_BOT_TOKEN
# - VK_ACCESS_TOKEN
# - DATABASE_URL=sqlite:///./smm.db

# Run
uvicorn main:app --reload --port 8000
```

Swagger docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

### Docker Stack

```bash
docker compose up -d --build
# Frontend: http://localhost:3000
# Backend: http://localhost:8000/docs
```

---

## 📊 Workflow

1. **Create Post:** Upload image/video, add title, description, select channels, set publish time
2. **Schedule:** Scheduler checks every 60 seconds for pending posts
3. **Publish:** When time arrives, post to all selected channels (Telegram, VK, Instagram)
4. **Manual:** Click "Publish Now" to publish immediately

---

## 🔧 Configuration

```bash
# Database
DATABASE_URL=sqlite:///./smm.db
# OR: postgresql://user:pass@host/dbname

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF

# VK
VK_ACCESS_TOKEN=vk123abc...

# Media
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800  # 50MB

# Scheduler
SCHEDULER_INTERVAL=60   # Check every 60 seconds
```

---

## 📁 Project Structure

```
smm-autoposter/
├── backend/
│   ├── main.py              # FastAPI entry
│   ├── routes/              # API endpoints
│   ├── services/            # Telegram, VK, Instagram clients
│   ├── scheduler.py         # APScheduler daemon
│   ├── uploads/             # Media storage
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/          # Dashboard, CreatePost, Channels, Analytics
│   │   ├── components/     # Reusable components
│   │   └── api.js          # Axios instance
│   └── package.json
├── docker-compose.yml
└── LICENSE
```

---

## 📖 Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design, API endpoints, database schema
- [LICENSE](LICENSE) - MIT License

---

**Author:** Kiiaara  
**Status:** Active Development
