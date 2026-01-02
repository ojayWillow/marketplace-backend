# Marketplace Backend - Comprehensive Testing Guide

## Quick Setup & Local Testing

This guide provides step-by-step instructions to test all API endpoints locally before deploying or building the frontend.

---

## PART 1: LOCAL SETUP (5 minutes)

### 1. Clone Repository
```bash
git clone https://github.com/ojayWillow/marketplace-backend.git
cd marketplace-backend
```

### 2. Create Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the Server
```bash
python wsgi.py
```

Expected output:
```
* Running on http://localhost:5000
* Press CTRL+C to quit
```

---

## PART 2: TESTING WORKFLOW (30-45 minutes)

### Health Check (Sanity Test)
```bash
curl -X GET http://localhost:5000/health
```

Expected Response:
```json
{"status": "ok"}
```

---

## TEST FLOW: Complete User Journey

Follow this sequence to test the entire workflow:

### STEP 1: User Registration
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser1",
    "email": "testuser1@example.com",
    "password": "SecurePass123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

Expected Response (201):
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "testuser1",
    "email": "testuser1@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

### STEP 2: User Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser1",
    "password": "SecurePass123"
  }'
```

Expected Response (200):
```json
{
  "message": "Login successful",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**IMPORTANT:** Save the token for the next requests. Export it:
```bash
export TOKEN="your_token_here"
```

### STEP 3: Create a Listing (Classifieds)
```bash
curl -X POST http://localhost:5000/api/listings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "iPhone 14 Pro - Excellent Condition",
    "description": "Used for 3 months, comes with original box and accessories",
    "category": "Electronics",
    "subcategory": "Phones",
    "condition": "like_new",
    "price": 800,
    "currency": "EUR",
    "location": "Riga, Latvia",
    "latitude": 56.9496,
    "longitude": 24.1052,
    "is_negotiable": true
  }'
```

Expected Response (201):
```json
{
  "message": "Listing created successfully",
  "listing": {
    "id": 1,
    "title": "iPhone 14 Pro - Excellent Condition",
    "seller": "testuser1",
    "status": "active"
  }
}
```

### STEP 4: Get All Listings
```bash
curl -X GET http://localhost:5000/api/listings
```

Expected: Array of all listings

### STEP 5: Create a Task (Quick Help)
```bash
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Dog Walking - Daily Walks Needed",
    "description": "Need someone to walk my golden retriever daily (30 mins morning + evening)",
    "category": "Pet Services",
    "budget": 15,
    "currency": "EUR",
    "location": "Riga",
    "latitude": 56.9496,
    "longitude": 24.1052,
    "deadline": "2026-02-01T18:00:00",
    "required_skills": ["animal_care", "responsibility"]
  }'
```

### STEP 6: Apply to a Task (Task Response)
```bash
# First, create another user to apply to the task
# Then login with that user and get the TOKEN2

curl -X POST http://localhost:5000/api/task_responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN2" \
  -d '{
    "task_id": 1,
    "message": "I am experienced with dogs and available daily!"
  }'
```

Expected Response (201):
```json
{
  "message": "Task response created",
  "response": {
    "id": 1,
    "task_id": 1,
    "user_id": 2,
    "is_accepted": false
  }
}
```

### STEP 7: Accept Task Response (Task Creator Only)
```bash
curl -X PUT http://localhost:5000/api/task_responses/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "is_accepted": true
  }'
```

### STEP 8: Create a Review (New Feature)
```bash
curl -X POST http://localhost:5000/api/reviews \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN2" \
  -d '{
    "rating": 5,
    "content": "Great service! Very professional and reliable.",
    "reviewed_user_id": 1,
    "task_id": 1
  }'
```

Expected Response (201):
```json
{
  "message": "Review created successfully",
  "review": {
    "id": 1,
    "rating": 5,
    "content": "Great service! Very professional and reliable.",
    "reviewer_id": 2,
    "reviewed_user_id": 1
  }
}
```

### STEP 9: Get User Profile
```bash
curl -X GET http://localhost:5000/api/auth/profile \
  -H "Authorization: Bearer $TOKEN"
```

---

## CRITICAL TESTS (Validation & Edge Cases)

### Test 1: Invalid Rating (Should Fail)
```bash
curl -X POST http://localhost:5000/api/reviews \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "rating": 10,
    "content": "Test",
    "reviewed_user_id": 1
  }'
```

Expected Response (400):
```json
{"error": "Rating must be between 1 and 5"}
```

### Test 2: Duplicate Task Application (Should Fail)
```bash
# Try to apply to same task twice with same user
curl -X POST http://localhost:5000/api/task_responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN2" \
  -d '{"task_id": 1, "message": "Applying again"}'
```

Expected Response (400):
```json
{"error": "Already applied to this task"}
```

### Test 3: Self-Application to Own Task (Should Fail)
```bash
curl -X POST http://localhost:5000/api/task_responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"task_id": 1}'
```

Expected Response (400):
```json
{"error": "Cannot apply to your own task"}
```

### Test 4: Missing JWT Token (Should Fail)
```bash
curl -X POST http://localhost:5000/api/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "content": "Test",
    "reviewed_user_id": 1
  }'
```

Expected Response (401):
```json
{"error": "Token is missing"}
```

### Test 5: Filter Reviews by User
```bash
curl -X GET "http://localhost:5000/api/reviews?reviewed_user_id=1"
```

Expected: List of reviews for user ID 1

---

## OPTIONAL: Testing with Postman

1. Download Postman: https://www.postman.com/downloads/
2. Create a new collection called "Marketplace API"
3. Add requests for each endpoint
4. Use Environment Variables for TOKEN and BASE_URL
5. Create tests in each request to validate responses

---

## SUCCESS CRITERIA (All Should Pass)

✅ Health check returns status=ok
✅ User registration creates account and returns user data
✅ User login returns valid JWT token
✅ Authenticated requests include token successfully
✅ Listings CRUD operations work (Create, Read, Update, Delete)
✅ Tasks CRUD operations work
✅ Task responses can be created and managed
✅ Reviews can be created with rating validation (1-5)
✅ Invalid ratings are rejected
✅ Duplicate applications are prevented
✅ Self-applications are prevented
✅ Missing tokens return 401
✅ Filtering and search work correctly
✅ Authorization checks prevent unauthorized operations

---

## COMMON ISSUES & SOLUTIONS

| Issue | Solution |
|-------|----------|
| Port 5000 already in use | Kill the process: `lsof -ti:5000 \| xargs kill -9` (macOS/Linux) or use Task Manager (Windows) |
| ModuleNotFoundError | Run `pip install -r requirements.txt` again |
| Database errors on first request | Normal - SQLite creates tables automatically |
| Token expired | Login again and get new token |
| 403 Unauthorized | Verify you have permission (e.g., task creator for accepting responses) |
| CORS errors from frontend | CORS is enabled - check frontend URL matches |

---

## Next Steps After Testing

1. ✅ **Backend validated** - All endpoints working
2. 🎯 **Frontend development** - Start building React/Vue UI
3. 📱 **Integration testing** - Test frontend + backend together
4. 🚀 **Deployment** - Deploy to production server

---

Happy testing! Report any issues found during testing.
