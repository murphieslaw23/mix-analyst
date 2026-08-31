# Mix Analyst

Mix Analyst is a full-stack application for analyzing long DJ mixes and continuous audio recordings. It provides automatic track detection (Shazam-style), BPM/key analysis, loudness measurement, and export tools.

## Stack

- **Web** — React + TypeScript + Vite + Tailwind CSS
- **API** — FastAPI + Pydantic v2 + SQLAlchemy 2
- **Worker** — Celery + Redis
- **Database** — PostgreSQL 16
- **Audio Analysis** — librosa, soundfile, shazamio, pyacoustid
- **Deployment** — Docker Compose

## Quickstart

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose

### Run with Docker

```bash
docker compose up --build
```

Once running:

- **Web**: http://localhost:3000
- **API**: http://localhost:8000
- **API Health**: http://localhost:8000/health/live

### Local Development

```bash
# API
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Worker
cd worker
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info

# Web
cd web
npm install
npm run dev
```

## Project Structure

```
mix-analyst/
├── api/                  # FastAPI backend
├── worker/               # Celery worker tasks
├── web/                  # React + Vite frontend
├── docker-compose.yml    # Local orchestration
├── .env.example          # Environment template
└── README.md
```

## Environment Variables

Copy the example file and adjust values for your setup:

```bash
cp .env.example .env
```

## License

All rights reserved.
