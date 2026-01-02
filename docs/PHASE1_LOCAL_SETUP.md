# PHASE 1: Local Testing & Validation Setup

## Quick Setup

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. PostgreSQL Setup
```bash
psql -U postgres
CREATE USER marketplace_user WITH PASSWORD 'marketplace_password';
CREATE DATABASE marketplace_db OWNER marketplace_user;
ALTER USER marketplace_user CREATEDB;
\\q
```

### 3. Configure .env
```bash
cp .env.example .env
# Edit .env with your local PostgreSQL connection details
FLASK_APP=wsgi.py
FLASK_ENV=development
DATABASE_URL=postgresql://marketplace_user:marketplace_password@localhost:5432/marketplace_db
JWT_SECRET_KEY=dev-secret-key-change-in-production
```

### 4. Initialize Database
```python
python
from app import create_app, db
app = create_app('development')
with app.app_context():
    db.create_all()
    print('Database initialized!')
exit()
```

### 5. Run Flask
```bash
flask run
```

## Testing with curl

### Register
```bash
curl -X POST http://localhost:5000/api/auth/register -H "Content-Type: application/json" -d '{"username":"test","email":"test@test.com","password":"pass123"}'
```

### Login
```bash
curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"pass123"}'
```

### Create Listing (replace TOKEN)
```bash
curl -X POST http://localhost:5000/api/listings -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d '{"title":"iPhone","description":"Good","category":"Electronics","price":500,"currency":"EUR","location":"Riga","latitude":56.9496,"longitude":24.1052}'
```

### Get Listings
```bash
curl http://localhost:5000/api/listings
```

### Create Task (replace TOKEN)
```bash
curl -X POST http://localhost:5000/api/tasks -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d '{"title":"Help needed","description":"Need assistance","category":"help","location":"Riga","latitude":56.9496,"longitude":24.1052}'
```

## Database Reset
```python
python
from app import create_app, db
app = create_app('development')
with app.app_context():
    db.drop_all()
    db.create_all()
    print('Database reset!')
exit()
```

Once all tests pass, move to Phase 2 backend enhancements.
