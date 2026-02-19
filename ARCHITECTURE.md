# Architecture — marketplace-backend

> Flask + PostgreSQL REST API that powers the Kolab marketplace.
> Deployed on Railway behind Gunicorn with gevent workers.

---

## High-Level Overview

```
Client (Next.js / React Native)
        │
        ▼
   Gunicorn + gevent  (wsgi.py / start.sh)
        │
        ▼
  Flask Application   (app/__init__.py  →  create_app())
   ├── JWT auth middleware  (before_request hook)
   ├── CORS (flask-cors)
   ├── Socket.IO (polling transport only)
   ├── Blueprints (app/routes/*)
   ├── SQLAlchemy ORM models (app/models/*)
   ├── Service layer (app/services/*)
   └── Utility helpers (app/utils/*)
        │
        ▼
   PostgreSQL (Railway-managed)
   Supabase Storage (images/files)
   Firebase Cloud Messaging (mobile push)
   Vonage SMS API (phone verification)
   Mailgun (transactional email)
```

---

## Application Factory

`app/__init__.py` exposes a `create_app(config_name)` factory that:

1. **Configures the database** — reads `DATABASE_URL` from the environment, rewrites
   `postgres://` → `postgresql://` for SQLAlchemy compatibility, falls back to
   SQLite for local dev and `:memory:` for tests.
2. **Initialises extensions** — `SQLAlchemy`, `Flask-Migrate`, `Flask-JWT-Extended`,
   `Flask-CORS`, `Flask-SocketIO`.
3. **Runs startup migrations** — after `db.create_all()` it uses `ALTER TABLE` to
   add any columns that `create_all` cannot add to existing tables (e.g.
   `attachment_url`, `onboarding_completed`).
4. **Registers a `before_request` hook** that decodes the JWT and calls
   `User.update_last_seen()` on every authenticated request (skips OPTIONS and
   public endpoints like `/health`, `/api/auth/login`, `/api/auth/register`).
5. **Registers blueprints** via `app.routes.register_routes(app)`.

Socket.IO is configured with **polling-only transport** (`allow_upgrades=False`)
because Gunicorn's standard gevent worker does not support WebSocket.

---

## Authentication & Authorisation

| Mechanism | Details |
|-----------|---------|
| Password hashing | `werkzeug.security` (generate / check password hash) |
| Token format | HS256 JWT issued at login/register, sent as `Authorization: Bearer <token>` |
| Token decoding | `flask_jwt_extended` + raw `PyJWT` decode in the `before_request` hook |
| Role checks | Route-level guards (e.g. admin routes check `user.is_admin` / `user.user_type`) |

Login and registration live in `app/routes/auth.py` and support both email/password
and phone-verified flows (Vonage SMS OTP).

---

## Database Schema (SQLAlchemy Models)

All models inherit `db.Model` and are defined in `app/models/`.

### Users (`users`)

Core identity table. Key columns: `username`, `email`, `phone`,
`password_hash`, `first_name`, `last_name`, `avatar_url`, `bio`,
`city`, `country`, `user_type` (`seller`|`buyer`|`helper`|`both`),
`is_helper`, `skills`, `helper_categories`, `hourly_rate`,
`latitude`/`longitude`, `reputation_score`, `completion_rate`,
`is_online`, `socket_id`, `last_seen`, `job_alert_preferences` (JSON text),
`onboarding_completed`. Provides `to_dict()` (private) and
`to_public_dict()` (public profile). Includes cached batch helpers for
review stats and completed task counts to avoid N+1 queries.

### Task Requests (`task_requests`)

Quick-help service tasks posted by clients. Key columns: `title`,
`description`, `category`, `budget`, `currency`, `difficulty`,
`location`, `latitude`/`longitude`, `creator_id` → `users`,
`assigned_to_id` → `users`, `radius`, `required_skills` (JSON),
`images` (JSON), `priority`, `status`
(`open`|`assigned`|`in_progress`|`completed`|`cancelled`),
`deadline`, `is_urgent`, `completed_at`.

### Task Applications (`task_applications`)

Join table: a helper applies to a task. Columns: `task_id` →
`task_requests`, `applicant_id` → `users`, `message`, `status`
(`pending`|`accepted`|`rejected`). Has a unique constraint on
`(task_id, applicant_id)`. Includes `to_dict_batch()` for efficient
serialisation with pre-fetched review stats.

### Listings (`listings`)

Buy/sell classifieds. Columns: `title`, `description`, `category`,
`subcategory`, `condition`, `price`, `currency`, `location`,
`latitude`/`longitude`, `seller_id` → `users`, `image_urls` (JSON),
`images` (text), `tags` (JSON), `views_count`, `listing_type`
(`sale`|`purchase`|`exchange`), `status`
(`active`|`sold`|`archived`|`pending`), `is_featured`, `is_negotiable`,
`expires_at`.

### Offerings (`offerings`)

Service advertisements (e.g. "Plumber — €20/hr"). Columns: `title`,
`description`, `category`, `location`, `latitude`/`longitude`,
`price`, `price_type` (`hourly`|`fixed`|`negotiable`), `currency`,
`status` (`active`|`paused`|`closed`), `creator_id` → `users`,
`availability`, `experience`, `service_radius`, `images` (JSON),
`contact_count`, `is_boosted`, `boost_expires_at`. Uses `lazy='joined'`
on the creator relationship for eager loading.

### Reviews (`reviews`)

Rating & feedback. Columns: `rating` (1-5 float), `content`,
`reviewer_id` → `users`, `reviewed_user_id` → `users`, `listing_id`
→ `listings`, `task_id` → `task_requests`, `review_type`
(`client_review`|`worker_review`).

### Conversations (`conversations`) & Messages (`messages`)

Real-time chat. Conversation links two participants
(`participant_1_id`, `participant_2_id`) and optionally a `task_id` or
`offering_id`. Message stores `conversation_id`, `sender_id`,
`content`, `is_read`, `attachment_url`, `attachment_type`
(`image`|`file`|`video`|`audio`).

### Notifications (`notifications`)

In-app notifications. Columns: `user_id`, `type` (see
`NotificationType` constants), `title`, `message`, `data` (JSON text
for i18n interpolation), `related_type`/`related_id` (for deep-link
navigation), `is_read`, `read_at`.

### Disputes (`disputes`)

Conflict resolution on tasks. Columns: `task_id`, `filed_by_id`,
`filed_against_id`, `reason` (one of 8 predefined values like
`work_quality`, `no_show`, etc.), `description`, `evidence_images`
(JSON), `status` (`open`|`under_review`|`resolved`), `resolution`,
`resolution_notes`, `resolved_by_id`, response fields.

### Favorites (`favorites`)

Defined in `app/models/favorite.py`. Lets users bookmark listings,
tasks, or offerings.

### Push Subscriptions (`push_subscriptions`)

Defined in `app/models/push_subscription.py`. Stores FCM / web-push
tokens per user.

### Password Resets (`password_resets`)

Defined in `app/models/password_reset.py`. Time-limited reset tokens.

### Translation Cache (`translation_caches`)

Defined in `app/models/translation_cache.py`. Caches translated
strings to avoid repeated API calls.

---

## Blueprint / Route Map

All blueprints are registered in `app/routes/__init__.py`:

| Blueprint | Prefix | File(s) | Purpose |
|-----------|--------|---------|---------|
| `health_bp` | `/api` | `routes/__init__.py` | `GET /api/health` — simple liveness check |
| `auth_bp` | `/api/auth` | `routes/auth.py` | Register, login, profile CRUD, password reset, phone verification |
| `onboarding_bp` | `/api/auth` | `routes/onboarding.py` | Post-registration onboarding flow |
| `listings_bp` | `/api/listings` | `routes/listings.py` | CRUD for buy/sell classifieds |
| `tasks_bp` | `/api/tasks` | `routes/tasks/` (sub-package) | CRUD for task requests + applications |
| `offerings_bp` | `/api/offerings` | `routes/offerings.py` | CRUD for service offerings |
| `reviews_bp` | `/api/reviews` | `routes/reviews.py` | Submit/view/manage reviews |
| `messages_bp` | `/api/messages` | `routes/messages.py` | Conversations & messages (REST + Socket.IO) |
| `notifications_bp` | `/api/notifications` | `routes/notifications.py` | List, read, mark-read notifications |
| `favorites_bp` | *(inline)* | `routes/favorites.py` | Add/remove/list favourites |
| `uploads_bp` | `/api/uploads` | `routes/uploads.py` | Image/file uploads to Supabase Storage |
| `push_bp` | `/api/push` | `routes/push.py` | Register/unregister push tokens, send test push |
| `disputes_bp` | `/api/disputes` | `routes/disputes.py` | File, respond-to, and resolve disputes |
| `admin_bp` | `/api/admin` | `routes/admin.py` | Admin dashboard: user management, stats, dispute resolution |

---

## Service Layer (`app/services/`)

| Service | File | Responsibility |
|---------|------|---------|
| Email | `email.py` | Mailgun transactional emails (password reset, welcome, etc.) |
| Firebase | `firebase.py` | Firebase Admin SDK init + FCM message sending |
| Push Notifications | `push_notifications.py` | High-level push: resolves user → tokens, builds payload, sends via Firebase |
| Storage | `storage.py` | Upload / delete files in Supabase Storage buckets |
| Job Alerts | `job_alerts.py` | Finds nearby helpers matching a new task and sends push notifications |
| Translation | `translation.py` | Text translation with DB-backed cache |
| Vonage SMS | `vonage_sms.py` | Phone verification OTP via Vonage API |

---

## Real-Time Layer (Socket.IO)

Defined in `app/socket_events.py`. Events:

- `connect` / `disconnect` — sets `user.is_online` and `socket_id`
- `join_conversation` / `leave_conversation` — room management
- `send_message` — persists message, emits to the room, sends push to offline recipient
- `typing` / `stop_typing` — typing indicators
- `mark_read` — marks messages as read, emits `messages_read` event

Transport is **long-polling only** (no WebSocket upgrade) due to
Gunicorn + gevent limitations.

---

## Middleware

There is one global `before_request` middleware registered in `create_app()`:

- **`update_last_seen`** — on every authenticated request, decodes the JWT from
  the `Authorization` header, loads the `User`, and calls
  `user.update_last_seen()`. Silently skips on invalid/missing tokens so
  unauthenticated endpoints are not affected.

Individual route files implement their own auth decorators inline (JWT
decode + user lookup at the top of each endpoint function).

---

## Deployment

| Component | Detail |
|-----------|--------|
| Host | Railway |
| Process manager | Gunicorn (`start.sh`) with gevent workers |
| WSGI entry | `wsgi.py` → `create_app()` |
| Database | Railway-managed PostgreSQL |
| Container | `Dockerfile` (Python 3.x) |
| Migrations | Flask-Migrate (Alembic) + startup `ALTER TABLE` safety net |
| File storage | Supabase Storage |
| Push | Firebase Cloud Messaging |
| SMS | Vonage |
| Email | Mailgun |
| CI | GitHub Actions (`.github/`) |

---

## Key Design Decisions

1. **Startup migrations** — `create_app()` runs `ALTER TABLE … ADD COLUMN`
   statements at boot because `db.create_all()` cannot add columns to existing
   tables. This avoids manual Alembic runs on every deploy.
2. **Batch stats helpers** — `User.get_review_stats_batch()` and
   `User.get_completed_tasks_batch()` load aggregate data for many users in a
   single query, used when serialising lists of applications.
3. **Polling-only Socket.IO** — intentional; Gunicorn's gevent worker cannot
   handle WebSocket upgrades without `geventwebsocket`.
4. **Dual image fields on Listing** — `image_urls` (JSON, legacy) and `images`
   (comma-separated text) coexist for backward compatibility.
