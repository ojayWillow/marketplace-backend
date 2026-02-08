# 🛒 Kolab Marketplace — Backend

Flask REST API powering the Kolab Marketplace — a Latvian platform for Buy/Sell classifieds, Quick Help task jobs, and Service Offerings. Built with PostgreSQL, Redis, JWT auth, Socket.IO real-time messaging, and Stripe payments.

## Live URLs

| Environment | URL |
|---|---|
| **Backend API** | [marketplace-backend-production-e808.up.railway.app](https://marketplace-backend-production-e808.up.railway.app/) |
| **Frontend** | [marketplace-frontend-tau-seven.vercel.app](https://marketplace-frontend-tau-seven.vercel.app) |
| **Supabase (Files/Images)** | [supabase.com/dashboard/project/fkxgqvcubfpqjwhiftej](https://supabase.com/dashboard/project/fkxgqvcubfpqjwhiftej) |

## Tech Stack

- **Python 3.11** + **Flask**
- **PostgreSQL** (primary database)
- **Redis** (caching, session management)
- **SQLAlchemy** ORM + **Flask-Migrate** (Alembic)
- **JWT** authentication (Flask-JWT-Extended)
- **Socket.IO** for real-time messaging & user presence
- **Stripe** payment integration
- **Supabase Storage** for image/file uploads
- **Twilio** SMS verification
- **Firebase** phone authentication
- **Docker** support

## Project Structure

```
marketplace-backend/
├── app/
│   ├── __init__.py           # Flask app factory, extensions, CORS
│   ├── models/               # SQLAlchemy models
│   │   ├── user.py           # User accounts, profiles, roles
│   │   ├── task_request.py   # Quick Help task/job posts
│   │   ├── task_application.py # Applications to tasks
│   │   ├── task_response.py  # Responses to tasks
│   │   ├── listing.py        # Buy/Sell classifieds
│   │   ├── offering.py       # Service offerings
│   │   ├── message.py        # Chat messages & conversations
│   │   ├── review.py         # User reviews & ratings
│   │   ├── dispute.py        # Dispute resolution system
│   │   ├── favorite.py       # Saved/favorited items
│   │   ├── notification.py   # Push & in-app notifications
│   │   ├── push_subscription.py # Push notification subscriptions
│   │   ├── password_reset.py # Password reset tokens
│   │   └── translation_cache.py # Translation caching
│   ├── routes/               # API route blueprints
│   │   ├── auth.py           # Registration, login, phone verify, password reset
│   │   ├── tasks/            # Task CRUD, search, map queries
│   │   ├── task_responses.py # Task response management
│   │   ├── listings.py       # Listing CRUD
│   │   ├── offerings.py      # Offering CRUD
│   │   ├── messages.py       # Conversations & messages
│   │   ├── reviews.py        # Review system
│   │   ├── disputes.py       # Dispute handling
│   │   ├── favorites.py      # Favorites management
│   │   ├── notifications.py  # Notification endpoints
│   │   ├── uploads.py        # File/image uploads (Supabase)
│   │   ├── push.py           # Push notification endpoints
│   │   ├── admin.py          # Admin dashboard endpoints
│   │   └── helpers.py        # Shared route utilities
│   ├── services/             # Business logic layer
│   ├── utils/                # Utility functions
│   └── socket_events.py      # Socket.IO event handlers (messaging, presence)
├── migrations/               # Alembic database migrations
├── tests/                    # Pytest test suite
├── scripts/                  # Utility scripts
├── Dockerfile                # Docker container config
├── docker-compose.yml        # Docker Compose (app + Postgres + Redis)
├── requirements.txt          # Python dependencies
├── wsgi.py                   # WSGI entry point
└── railway.json              # Railway deployment config
```

## Getting Started

### Prerequisites

- **Python 3.11**
- **PostgreSQL** (local or cloud)
- **Redis** (local or cloud)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/ojayWillow/marketplace-backend.git
cd marketplace-backend

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your database URL, API keys, etc.

# Initialize the database
python init_db.py

# Run development server (http://localhost:5000)
python wsgi.py
```

### Docker Setup

```bash
docker-compose up --build
```

This starts the Flask app, PostgreSQL, and Redis together.

### Running Tests

```bash
pip install -r requirements-test.txt
pytest
```

## Environment Variables

See `.env.example` for the full list. Key variables:

- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `JWT_SECRET_KEY` — Secret for JWT token signing
- `SUPABASE_URL` / `SUPABASE_KEY` — Supabase project for file storage
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` — SMS verification
- `STRIPE_SECRET_KEY` — Payment processing
- `FIREBASE_*` — Firebase phone auth config

## API Routes Overview

| Module | Prefix | Description |
|---|---|---|
| Auth | `/api/auth` | Register, login, phone verify, password reset, Firebase auth |
| Tasks | `/api/tasks` | Quick Help job CRUD, search, map-based queries |
| Task Responses | `/api/task-responses` | Apply to / manage task responses |
| Listings | `/api/listings` | Buy/Sell classifieds CRUD |
| Offerings | `/api/offerings` | Service offerings CRUD |
| Messages | `/api/messages` | Conversations, send/receive messages |
| Reviews | `/api/reviews` | User reviews and ratings |
| Disputes | `/api/disputes` | Dispute resolution system |
| Favorites | `/api/favorites` | Save/unsave items |
| Notifications | `/api/notifications` | In-app notification management |
| Uploads | `/api/uploads` | File/image uploads to Supabase Storage |
| Push | `/api/push` | Push notification subscriptions |
| Admin | `/api/admin` | Admin dashboard, user management, moderation |

## Real-time Features

Socket.IO handles:
- **Live messaging** — instant message delivery in conversations
- **User presence** — online/offline status tracking
- **Typing indicators** — real-time typing status

## Deployment

Currently deployed on **Railway** with auto-deploys from the `main` branch.

- Railway config: `railway.json`
- Start command: `start.sh` (runs Gunicorn with eventlet for Socket.IO)
- Database: Railway-managed PostgreSQL
- Redis: Railway-managed Redis

## Related Repositories

- **Frontend:** [ojayWillow/marketplace-frontend](https://github.com/ojayWillow/marketplace-frontend) — React web app + Expo mobile app

---

## Current Status (Feb 2026)

- ✅ All API endpoints functional
- ✅ Migrated from Render to **Railway** for backend hosting
- ✅ Supabase for file/image storage
- ✅ Real-time messaging and presence working
- ✅ Dispute resolution system implemented
- 🔧 Frontend mobile view tweaks in progress
