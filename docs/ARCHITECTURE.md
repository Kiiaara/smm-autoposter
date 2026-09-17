# 🏗️ SMM Autoposter Architecture

## Overview

Full-stack social media automation: FastAPI backend + React frontend for scheduling and auto-posting content to Telegram, VK, Instagram, and more.

---

## 🔄 System Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      Frontend (React)                      │
│              (http://localhost:5173)                       │
├────────────────────────────────────────────────────────────┤
│  • Content upload UI (title, description, image, video)   │
│  • Scheduler (set times, days, recurring)                 │
│  • Channel settings (add Telegram, VK, Instagram)         │
│  • Analytics dashboard (posts published, engagement)      │
└────────────────┬─────────────────────────────────────────┘
                 │ HTTP/REST API
                 ▼
┌────────────────────────────────────────────────────────────┐
│             Backend (FastAPI)                              │
│            (http://localhost:8000)                         │
├────────────────────────────────────────────────────────────┤
│  Router                      Database           Scheduler  │
│  ├─ POST /posts             SQLite: smm.db    APScheduler │
│  ├─ GET /schedule           ├─ posts          ├─ Check    │
│  ├─ POST /channels          ├─ channels       │  every    │
│  ├─ PUT /channels/{id}      ├─ schedules      │  60 sec   │
│  ├─ DELETE /posts/{id}      ├─ users          │          │
│  ├─ POST /publish (manual)  └─ config         └─ Publish  │
│  └─ GET /analytics                                        │
│       │                                                    │
│       ├─ Content Processor (image resize, encode)        │
│       ├─ API Clients (Telegram, VK, Instagram)           │
│       └─ Error Logger (database)                         │
└────────────┬────────────────────────────────────────┬──────┘
             │                                        │
    ┌────────▼────────┐                  ┌────────────▼────────┐
    │  External APIs  │                  │   Local Storage    │
    ├─────────────────┤                  ├────────────────────┤
    │ • Telegram API  │                  │ /uploads/          │
    │ • VK API        │                  │  ├─ images/        │
    │ • Instagram API │                  │  ├─ videos/        │
    │ • Max API       │                  │  └─ thumbnails/    │
    └─────────────────┘                  └────────────────────┘
```

---

## 📊 Data Flow

### Content Upload
```
Frontend (user uploads image + text)
        │
        ▼
API: POST /posts {title, description, media, channel_ids}
        │
        ▼
Backend: 
  1. Save to database (pending status)
  2. Store image: /uploads/images/{uuid}.jpg
  3. Generate thumbnail: /uploads/thumbnails/{uuid}.jpg
  4. Return post ID + preview URL
        │
        ▼
Frontend: Display upload success
```

### Scheduled Publishing
```
Backend Scheduler (every 60 sec)
        │
        ▼
Query: SELECT * FROM posts WHERE publish_time <= NOW() AND status='pending'
        │
        ▼
For each post:
  1. Load media from /uploads/
  2. Prepare payload (title, image, link)
  3. Send to each channel API (Telegram, VK, etc.)
  4. Handle response (success/error)
  5. Update DB: status='published' + timestamp
        │
        ▼
Log results: success_count, error_count
```

### Channel Settings
```
Add Telegram Channel:
  1. Get bot_token from user
  2. Get chat_id (from Telegram)
  3. Test connection: GET /getMe
  4. Store in DB: channels table
  5. Use for future posts
```

---

## 🗄️ Database Schema

### SQLite (smm.db)

```sql
-- Posts table
CREATE TABLE posts (
  id TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  media_url TEXT,
  channels TEXT,  -- JSON array of channel IDs
  publish_time DATETIME,
  status TEXT,    -- 'pending', 'published', 'failed'
  created_at DATETIME,
  updated_at DATETIME
);

-- Channels table
CREATE TABLE channels (
  id TEXT PRIMARY KEY,
  platform TEXT,      -- 'telegram', 'vk', 'instagram'
  bot_token TEXT,     -- encrypted
  chat_id TEXT,
  name TEXT,
  active BOOLEAN
);

-- Schedules table (recurring posts)
CREATE TABLE schedules (
  id TEXT PRIMARY KEY,
  name TEXT,
  days TEXT,          -- JSON ["monday", "wednesday"]
  time TEXT,          -- "10:00"
  content_template TEXT,
  channels TEXT       -- JSON array
);

-- Users table
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE,
  password_hash TEXT,
  email TEXT,
  created_at DATETIME
);

-- Config table
CREATE TABLE config (
  key TEXT PRIMARY KEY,
  value TEXT
);
```

---

## 🔧 API Endpoints

### Posts
```
POST /posts
  ├─ Create new post
  ├─ Body: {title, description, media, channel_ids, publish_time}
  └─ Response: {id, preview_url, status}

GET /posts
  ├─ List all posts (with pagination)
  └─ Query params: ?status=pending&page=1&limit=20

PUT /posts/{id}
  ├─ Edit post (only if status='pending')
  └─ Body: {title, description, media, publish_time}

DELETE /posts/{id}
  └─ Cancel/delete post (before publishing)

POST /posts/{id}/publish
  ├─ Manual publish (publish now, don't wait for scheduled time)
  └─ Response: {status, results_per_channel}
```

### Channels
```
POST /channels
  ├─ Add channel
  ├─ Body: {platform, bot_token, chat_id, name}
  └─ Test connection before saving

GET /channels
  └─ List all configured channels

PUT /channels/{id}
  └─ Edit channel settings

DELETE /channels/{id}
  └─ Remove channel
```

### Schedules
```
POST /schedules
  ├─ Create recurring schedule
  ├─ Body: {name, days, time, content_template, channel_ids}
  └─ Example: {"name": "Daily morning post", "days": ["mon"-"fri"], "time": "09:00"}

GET /schedules
  └─ List all schedules

PUT /schedules/{id}
  └─ Edit schedule

DELETE /schedules/{id}
  └─ Disable schedule
```

### Analytics
```
GET /analytics
  ├─ Dashboard data
  └─ Response: {total_posts, published_count, failed_count, channels_active}

GET /analytics/logs
  └─ Detailed error logs (for debugging)
```

---

## 🌐 External API Integration

### Telegram API
```python
# Send message with image
POST https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto
{
  "chat_id": "-1001234567890",
  "photo": binary_image_data,
  "caption": "Post title\n\nDescription",
  "parse_mode": "HTML"
}
```

### VK API
```python
# Upload photo + post
1. POST /photos.getUploadServer (get upload URL)
2. POST {upload_url} (upload image)
3. POST /photos.saveWallPhoto (save to VK)
4. POST /wall.post (publish with photo)
```

### Instagram API (Meta)
```python
# Note: Instagram has restrictions, limited API access
# Usually requires Instagram Graph API + business account
# Simplified: Store for manual posting or use Instagram.Business automation
```

---

## 📁 Project Structure

```
smm-autoposter/
├── backend/
│   ├── main.py                  (FastAPI app entry)
│   ├── config.py                (load .env)
│   ├── database.py              (SQLite setup)
│   ├── models.py                (Pydantic models)
│   ├── routes/
│   │   ├── posts.py
│   │   ├── channels.py
│   │   ├── schedules.py
│   │   └── analytics.py
│   ├── services/
│   │   ├── telegram_client.py
│   │   ├── vk_client.py
│   │   ├── instagram_client.py
│   │   └── media_processor.py
│   ├── scheduler.py             (APScheduler init)
│   ├── requirements.txt
│   ├── .env.example
│   └── uploads/                 (media storage)
│       ├── images/
│       ├── videos/
│       └── thumbnails/
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── CreatePost.jsx
│   │   │   ├── SchedulePost.jsx
│   │   │   ├── Channels.jsx
│   │   │   └── Analytics.jsx
│   │   ├── components/
│   │   │   ├── PostForm.jsx
│   │   │   ├── ChannelList.jsx
│   │   │   ├── ScheduleEditor.jsx
│   │   │   └── AnalyticsChart.jsx
│   │   └── api.js               (axios instance)
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
│
├── docker-compose.yml
├── nginx.conf                   (if using Nginx)
└── README.md
```

---

## 🚀 Deployment

### Local Development
```bash
# Terminal 1: Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Production (VPS)
```
┌─────────────────────────────────┐
│        Nginx (reverse proxy)    │
│  :80 → /api/* → backend:8000   │
│  :80 → / → frontend (dist/)    │
├─────────────────────────────────┤
│  Backend (uvicorn :8000)        │
│  ├─ APScheduler daemon          │
│  └─ SQLite database             │
├─────────────────────────────────┤
│  Frontend (dist/ static files)  │
└─────────────────────────────────┘
```

---

## 🔐 Security

- ✅ API keys encrypted in database
- ✅ CORS configured (frontend URL only)
- ✅ Rate limiting on POST endpoints
- ✅ File upload validation (image size, format)
- ⚠️ HTTPS recommended for production
- ⚠️ Database backups essential (posts lost otherwise)

---

## ⚡ Performance

| Metric | Value |
|--------|-------|
| Media upload | <5s |
| Publish to all channels | ~2-3s |
| API response | <500ms |
| Database query | <100ms |
| Memory usage | ~200MB |

---

## 📈 Monitoring

- Log file: `backend/logs/app.log`
- Database health: `SELECT COUNT(*) FROM posts WHERE status='failed'`
- Scheduler check: APScheduler logs in stdout

---

## 🔮 Future Enhancements

- [ ] Support YouTube, Twitter, LinkedIn
- [ ] Content preview before publish
- [ ] A/B testing (multiple versions)
- [ ] Analytics/engagement tracking
- [ ] OCR + auto-captioning (for images)
- [ ] Video transcoding
- [ ] User authentication/multi-account

