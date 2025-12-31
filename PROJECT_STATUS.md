# Marketplace Backend - Project Status & Quick Start Guide

## Project Overview
**Latvian Marketplace Platform** - A Flask-based backend API for a multi-segment marketplace platform

**Two Main Segments:**
1. **Buy/Sell Classifieds** - Traditional classified ads marketplace (like ss.com)
2. **Quick Help Services** - Task posting and request fulfillment platform (e.g., dog walking, furniture help, professional services)

**Key Features:**
- User authentication with JWT tokens
- Listing management for classifieds
- Task request creation and management
- PostgreSQL database with Redis caching
- Stripe payment integration
- CORS enabled for frontend integration
- Docker & Docker Compose support
- SQLite for local development (PostgreSQL for production)

---

## Current Status: READY FOR LOCAL TESTING ✅

### Completed:
- [x] Backend API structure (Flask application)
- [x] Database models (User, Listing, TaskRequest)
- [x] Authentication routes (register, login, profile)
- [x] Listings routes (CRUD operations for classifieds)
- [x] Tasks routes (CRUD operations for quick help services)
- [x] Health check endpoint
- [x] Dependencies configured (requirements.txt)
- [x] Docker & Docker Compose setup
- [x] API Testing Guide with curl examples
- [x] All indentation errors fixed
- [x] SQLite configured for local development

### Current Architecture:
```
marketplace-backend/
├── app/
│   ├── __init__.py          # Flask app factory & configuration
│   ├── models/              # Database models
│   │   ├── __init__.py
│   │   ├── user.py         # User model
│   │   ├── listing.py      # Listing model (classifieds)
│   │   └── task_request.py # TaskRequest model (quick help)
│   └── routes/              # API routes
│       ├── __init__.py
│       ├── auth.py         # /api/auth/* endpoints
│       ├── listings.py     # /api/listings/* endpoints
│       └── tasks.py        # /api/tasks/* endpoints
├── wsgi.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container configuration
├── docker-compose.yml      # Multi-container orchestration
├── .env.example            # Environment variables template
├── API_TESTING_GUIDE.md    # Testing instructions
└── README.md               # Project documentation
```

---

## Quick Start (LOCAL DEVELOPMENT)

### Prerequisites:
- Python 3.11+
- pip
- Git

### Setup Instructions:

#### 1. Clone and Navigate:
```bash
git clone https://github.com/ojayWillow/marketplace-backend.git
cd marketplace-backend
```

#### 2. Create Virtual Environment:
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies:
```bash
pip install -r requirements.txt
```

#### 4. Run the Application:
```bash
python wsgi.py
```

Server will start at: `http://localhost:5000`

#### 5. Test Health Endpoint:
```bash
# PowerShell
Invoke-WebRequest -Uri http://localhost:5000/health

# Or with curl
curl -X GET http://localhost:5000/health
```

Expected Response:
```json
{"status": "ok"}
```

---

## API Endpoints Overview

### Health Check
- `GET /health` - Server status check

### Authentication (`/api/auth/`)
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - User login
- `GET /api/auth/profile` - Get user profile

### Listings - Buy/Sell Classifieds (`/api/listings/`)
- `GET /api/listings` - List all classifieds
- `POST /api/listings` - Create new listing
- `GET /api/listings/<id>` - Get listing details
- `PUT /api/listings/<id>` - Update listing
- `DELETE /api/listings/<id>` - Delete listing

### Tasks - Quick Help Services (`/api/tasks/`)
- `GET /api/tasks` - List all task requests
- `POST /api/tasks` - Create new task request
- `GET /api/tasks/<id>` - Get task details
- `PUT /api/tasks/<id>` - Update task
- `DELETE /api/tasks/<id>` - Delete task

---

## Docker Deployment (Optional)

### Using Docker Compose:
```bash
docker-compose up
```

This starts three services:
- **web** (Flask API) - Port 5000
- **db** (PostgreSQL) - Port 5432
- **redis** (Cache) - Port 6379

### Using Docker Only:
```bash
docker build -t marketplace-backend .
docker run -p 5000:5000 marketplace-backend
```

---

## Testing the API

See `API_TESTING_GUIDE.md` for complete curl/Postman examples.

### Quick Test Example:
```bash
# Register user
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

---

## Project Structure Notes

### Database
- **Local Dev**: SQLite (sqlite:///marketplace.db)
- **Production**: PostgreSQL (update DATABASE_URI in app/__init__.py)

### Configuration
- Environment variables in `.env` file
- See `.env.example` for required variables

### Routes Registration
- All routes automatically registered via `register_routes()` function
- Routes packaged as Flask blueprints
- Error handling with try/except blocks

---

## Common Issues & Solutions

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution**: `pip install -r requirements.txt`

### Issue: "Port 5000 already in use"
**Solution**: Change port in wsgi.py or kill process using port 5000

### Issue: Database errors on API calls
**Solution**: This is normal for first requests. Database tables auto-create on first API call.

### Issue: CORS errors from frontend
**Solution**: CORS already enabled. Check frontend URL in browser console.

---

## Next Steps / Development Roadmap

### Phase 1: Testing & Validation ✅ CURRENT
1. Clone repository
2. Set up virtual environment
3. Install dependencies
4. Run `python wsgi.py`
5. Test endpoints with curl or Postman

### Phase 2: Frontend Development (Next)
1. Build React/Vue frontend
2. Integrate with backend API endpoints
3. Implement user authentication UI
4. Create listing browsing interface
5. Create task posting interface

### Phase 3: Production Deployment
1. Switch to PostgreSQL database
2. Configure environment variables
3. Set up cloud hosting (AWS, Heroku, etc.)
4. Deploy with Docker Compose
5. Configure SSL/HTTPS
6. Set up CI/CD pipeline

### Phase 4: Advanced Features
1. Payment processing (Stripe integration)
2. Real-time notifications
3. Search and filtering
4. User ratings and reviews
5. Admin dashboard
6. Analytics and reporting

---

## Important Files

| File | Purpose |
|------|----------|
| `app/__init__.py` | Flask app initialization & configuration |
| `wsgi.py` | Entry point for running the application |
| `requirements.txt` | Python package dependencies |
| `Dockerfile` | Container image configuration |
| `docker-compose.yml` | Multi-container orchestration |
| `.env.example` | Environment variables template |
| `API_TESTING_GUIDE.md` | Testing instructions with examples |

---

## Support & Documentation

- **API Testing**: See `API_TESTING_GUIDE.md`
- **Full Setup**: See `README.md`
- **Questions**: Check code comments in each module

---

## Database Initialization

Database tables are created automatically when:
1. Flask app initializes with `db.init_app(app)`
2. First database query is made

To manually create tables (if needed):
```python
from app import create_app
app = create_app()
with app.app_context():
    from app.models import User, Listing, TaskRequest
    db.create_all()
```

---

## Current Version
**Backend v0.1.0** - Foundation Complete
- All core APIs operational
- Database models ready
- Ready for frontend integration
- Ready for API testing

**Last Updated**: Latest commit fixing indentation in app/__init__.py
**Database**: SQLite (Local) / PostgreSQL (Production)
**Status**: READY FOR LOCAL TESTING ✅
