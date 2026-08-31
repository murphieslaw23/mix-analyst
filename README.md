# Mix Analyst

Mix Analyst is a full-stack application for analyzing mixes, built with a web frontend, an API backend, and Docker-based deployment.

## Stack

- **Web** — frontend application
- **API** — backend service
- **Docker** — containerized development and deployment

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose

### Run with Docker

```bash
docker compose up --build
```

Once running:

- Web: http://localhost:3000
- API: http://localhost:8000

### Local Development

```bash
# Frontend
cd web
npm install
npm run dev

# API
cd api
npm install
npm run dev
```

## Project Structure

```
mix-analyst/
├── web/                  # Frontend application
├── api/                  # Backend API
├── docker-compose.yml    # Local orchestration
├── Dockerfile            # Container build
├── .gitignore
└── README.md
```

## Environment Variables

Copy the example file and adjust values for your setup:

```bash
cp .env.example .env
```

## License

All rights reserved.
