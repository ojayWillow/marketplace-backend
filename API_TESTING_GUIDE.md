# Marketplace API Testing Guide

This guide provides instructions for testing the marketplace backend API using curl and Postman.

## Prerequisites

1. **Start the Backend Server**
```bash
# Navigate to the project directory
cd marketplace-backend

# Activate virtual environment
venv\Scripts\activate

# Run the Flask application
python wsgi.py
```

The server will start on `http://localhost:5000`

## 1. Health Check

**Test if the server is running:**

```bash
curl -X GET http://localhost:5000/health
```

**Expected Response (200 OK):**
```json
{"status": "ok"}
```

---

## 2. Authentication Endpoints

### 2.1 Register a New User

```bash
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

**Expected Response (201 Created):**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    ...
  }
}
```

### 2.2 Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123"
  }'
```

**Expected Response (200 OK):**
```json
{
  "message": "Login successful",
  "token": "eyJhbGc...",
  "user": {...}
}
```

Save the token for authenticated requests!

### 2.3 Get User Profile

```bash
curl -X GET http://localhost:5000/api/auth/profile \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 3. Listings (Buy/Sell) Endpoints

### 3.1 Create a Listing

```bash
curl -X POST http://localhost:5000/api/listings \
  -H "Content-Type: application/json" \
  -d '{
    "title": "iPhone 12 Pro",
    "description": "Like new, barely used",
    "category": "electronics",
    "price": 850.00,
    "seller_id": 1,
    "location": "Riga, Latvia",
    "latitude": 56.9496,
    "longitude": 24.1052,
    "condition": "like_new"
  }'
```

### 3.2 Get All Listings

```bash
curl -X GET "http://localhost:5000/api/listings?page=1&per_page=20&status=active"
```

### 3.3 Get Single Listing

```bash
curl -X GET http://localhost:5000/api/listings/1
```

### 3.4 Update Listing

```bash
curl -X PUT http://localhost:5000/api/listings/1 \
  -H "Content-Type: application/json" \
  -d '{
    "price": 800.00,
    "status": "sold"
  }'
```

### 3.5 Delete Listing

```bash
curl -X DELETE http://localhost:5000/api/listings/1
```

---

## 4. Task Requests (Quick Help) Endpoints

### 4.1 Create a Task Request

```bash
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Help moving furniture",
    "description": "Need help moving a sofa to 3rd floor",
    "category": "moving",
    "creator_id": 1,
    "location": "Riga, Latvia",
    "latitude": 56.9496,
    "longitude": 24.1052,
    "budget": 50.00,
    "priority": "high"
  }'
```

### 4.2 Get Nearby Tasks (with geolocation)

```bash
curl -X GET "http://localhost:5000/api/tasks?latitude=56.9496&longitude=24.1052&radius=5&status=open"
```

### 4.3 Get Single Task

```bash
curl -X GET http://localhost:5000/api/tasks/1
```

### 4.4 Accept Task (Assign to Helper)

```bash
curl -X POST http://localhost:5000/api/tasks/1/accept \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 2
  }'
```

### 4.5 Complete Task

```bash
curl -X POST http://localhost:5000/api/tasks/1/complete
```

---

## Using Postman

1. **Import Collection**: Create a new Postman collection
2. **Add Environment Variables**:
   - `base_url`: http://localhost:5000
   - `token`: (paste JWT token here after login)
3. **Create Requests**: Use the curl examples above to create Postman requests
4. **Add Authorization**: For protected endpoints, set Authorization header to `Bearer {{token}}`

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `Connection refused` | Ensure Flask server is running on port 5000 |
| `401 Unauthorized` | Make sure JWT token is included in Authorization header |
| `400 Bad Request` | Check JSON payload is valid and matches schema |
| `PostgreSQL connection error` | Verify database is running and credentials in .env are correct |

---

## Next Steps

1. Install required packages: `pip install -r requirements.txt`
2. Set up PostgreSQL database
3. Run migrations
4. Start testing with the guide above
