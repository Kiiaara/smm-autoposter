# SMM Autoposter

Автопостинг в Telegram, ВКонтакте, Instagram (заглушка), Max (заглушка).

## Быстрый старт

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # заполнить .env при необходимости
uvicorn main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Открыть: http://localhost:5173

## Настройка

1. Зайти в Настройки - Каналы - добавить Telegram канал (bot_token + chat_id)
2. Настройки - Расписание - добавить временные слоты
3. Настройки - Бот напоминаний - вставить токен и свой chat_id

## Деплой на VPS

```bash
# backend как systemd service (uvicorn на :8000)
# frontend: npm run build -> dist/ отдаётся Nginx
# Nginx: location /api/ { proxy_pass http://localhost:8000/api/; }
#        location /uploads/ { proxy_pass http://localhost:8000/uploads/; }
```

Обязательно установить `BASE_URL=https://ваш-домен.ru` в `.env`
чтобы Telegram мог скачивать медиафайлы.
