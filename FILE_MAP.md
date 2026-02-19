# File Map — marketplace-backend

> Every file and directory in the repository with a one-line description.

---

## Root

```
.env.example              Environment variable template (DB URL, JWT secret, API keys)
.gitignore                Git ignore rules
.python-version           Python version pin (used by pyenv)
Dockerfile                Container image definition for Railway
docker-compose.yml        Local dev: spins up PostgreSQL + app
init_db.py                Standalone script: create all DB tables from scratch
migrate_debug.py          Debug helper for Alembic migration issues
patched_app.py            Monkey-patched app entry point (gevent compatibility)
pytest.ini                Pytest configuration (markers, paths)
railway.json              Railway platform build/deploy settings
requirements.txt          Production Python dependencies
requirements-test.txt     Additional test-only dependencies (pytest, etc.)
reset_db.py               Standalone script: drop and recreate all tables
run_migration.py          Standalone script: run pending Alembic migrations
start.sh                  Production entrypoint: applies migrations, starts Gunicorn
wsgi.py                   WSGI entry point — calls create_app(), used by Gunicorn
```

## Documentation (`docs/`, root `.md` files)

```
README.md                 Project overview, setup instructions, API summary
AI_ASSISTANT_PROMPT.md    Prompt context for AI coding assistants
PRODUCTION_URLS.md        Production URLs and environment details
PROJECT_STATUS.md         Current feature status and known issues
RAILWAY_SETUP.md          Step-by-step Railway deployment guide
```

## Application Package (`app/`)

```
app/__init__.py           Application factory (create_app), extension init, startup migrations, before_request middleware
app/socket_events.py      Socket.IO event handlers (connect, disconnect, messaging, typing, read receipts)
```

## Models (`app/models/`)

```
app/models/__init__.py          Re-exports all model classes for convenient imports
app/models/user.py              User model — auth, profile, presence, job alert prefs, batch stat helpers
app/models/task_request.py      TaskRequest model — quick-help tasks posted by clients
app/models/task_application.py  TaskApplication model — helper applies to a task (unique constraint)
app/models/listing.py           Listing model — buy/sell classifieds
app/models/offering.py          Offering model — service advertisements with boost support
app/models/review.py            Review model — 1-5 star ratings between users
app/models/message.py           Conversation + Message models — real-time chat with attachments
app/models/notification.py      Notification model + NotificationType constants
app/models/dispute.py           Dispute model — task conflict resolution with evidence
app/models/favorite.py          Favorite model — user bookmarks for listings/tasks/offerings
app/models/push_subscription.py PushSubscription model — FCM/web-push token storage
app/models/password_reset.py    PasswordReset model — time-limited reset tokens
app/models/translation_cache.py TranslationCache model — caches translated strings
```

## Routes (`app/routes/`)

```
app/routes/__init__.py      Blueprint registry — register_routes() binds all blueprints to the app
app/routes/auth.py          /api/auth — register, login, profile get/update, password reset, phone verify
app/routes/onboarding.py    /api/auth — post-registration onboarding completion
app/routes/listings.py      /api/listings — CRUD for classifieds (create, list, get, update, delete)
app/routes/tasks/           /api/tasks — sub-package for task request + application endpoints
app/routes/offerings.py     /api/offerings — CRUD for service offerings (list, create, update, delete, boost)
app/routes/reviews.py       /api/reviews — submit, list, manage reviews; review eligibility checks
app/routes/messages.py      /api/messages — conversations list, message history, send message, mark read
app/routes/notifications.py /api/notifications — list, unread count, mark read, mark all read
app/routes/favorites.py     /api/favorites — add, remove, list user favourites
app/routes/uploads.py       /api/uploads — image/file upload to Supabase Storage
app/routes/push.py          /api/push — register/unregister push tokens, send test notification
app/routes/disputes.py      /api/disputes — file dispute, respond, view, resolve
app/routes/admin.py         /api/admin — admin dashboard stats, user management, dispute resolution
app/routes/helpers.py       Shared route helper functions (pagination, error formatting)
```

## Services (`app/services/`)

```
app/services/__init__.py          Package init
app/services/email.py             Mailgun email sending (password reset, welcome emails)
app/services/firebase.py          Firebase Admin SDK initialisation + raw FCM send
app/services/push_notifications.py High-level push notification dispatch (user → tokens → Firebase)
app/services/storage.py           Supabase Storage upload/delete (images, files)
app/services/job_alerts.py        Matches new tasks to nearby helpers and sends push alerts
app/services/translation.py       Text translation with DB-backed caching
app/services/vonage_sms.py        Vonage SMS API — send OTP, verify code for phone verification
```

## Utilities (`app/utils/`)

```
app/utils/                  Shared utility functions used across routes and services
```

## Constants (`app/constants/`)

```
app/constants/              Application-wide constant values (categories, status enums, etc.)
```

## Migrations (`migrations/`)

```
migrations/                 Alembic migration scripts (auto-generated by Flask-Migrate)
```

## Scripts (`scripts/`)

```
scripts/                    Operational/maintenance scripts
```

## Tests (`tests/`)

```
tests/                      Pytest test suite
```

## CI/CD (`.github/`)

```
.github/                    GitHub Actions workflows (CI, deployment)
```
