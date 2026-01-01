# Marketplace Backend - API Endpoints Testing Guide

## Phase 2: Complete API Testing

This guide provides PowerShell commands to test all authentication and core endpoints.

### Prerequisites

1. Flask server running: `python wsgi.py`
2. Database initialized: `python init_db.py`
3. All endpoints are at: `http://127.0.0.1:5000`

---

## 1. Health Check Endpoint

**Endpoint:** `GET /health`
**Purpose:** Verify Flask app is running
**Status Code:** 200 OK

```powershell
$response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -UseBasicParsing
Write-Host "Status: $($response.StatusCode)"
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

**Expected Response:**
```json
{
  "status": "ok"
}
```

---

## 2. User Registration Endpoint

**Endpoint:** `POST /api/auth/register`
**Purpose:** Create new user account
**Status Code:** 201 Created

```powershell
$body = @{
    username = "testuser"
    email = "test@example.com"
    password = "testpassword123"
    first_name = "Test"
    last_name = "User"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/auth/register" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body `
    -UseBasicParsing

Write-Host "Status: $($response.StatusCode)"
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

**Expected Response:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User",
    "is_active": true,
    "user_type": "both"
    ...
  }
}
```

---

## 3. User Login Endpoint

**Endpoint:** `POST /api/auth/login`
**Purpose:** Authenticate user and receive JWT token
**Status Code:** 200 OK

```powershell
$body = @{
    email = "test@example.com"
    password = "testpassword123"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body `
    -UseBasicParsing

Write-Host "Status: $($response.StatusCode)"
$loginResponse = $response.Content | ConvertFrom-Json
$loginResponse | ConvertTo-Json

# Save token for next request
$token = $loginResponse.token
Write-Host "Token: $token"
```

**Expected Response:**
```json
{
  "message": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "testuser",
    ...
  }
}
```

---

## 4. Get User Profile Endpoint

**Endpoint:** `GET /api/auth/profile`
**Purpose:** Retrieve current user profile (requires JWT token)
**Status Code:** 200 OK

```powershell
# Use token from login response
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

$headers = @{
    "Authorization" = "Bearer $token"
}

$response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/auth/profile" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

Write-Host "Status: $($response.StatusCode)"
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

**Expected Response:**
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "first_name": "Test",
  "last_name": "User",
  "is_active": true,
  "user_type": "both"
  ...
}
```

---

## Testing Workflow

### Step 1: Health Check
```powershell
# Verify Flask is running
invoke-webrequest http://127.0.0.1:5000/health -UseBasicParsing
```

### Step 2: Register New User
```powershell
# Create user account
# Copy the token from login response for next step
```

### Step 3: Login
```powershell
# Authenticate and get JWT token
# Save the token value
```

### Step 4: Get Profile
```powershell
# Use token in Authorization header
# Should return user profile data
```

---

## Error Responses

### Invalid Credentials
**Status:** 401 Unauthorized
```json
{
  "error": "Invalid email or password"
}
```

### Missing Token
**Status:** 401 Unauthorized
```json
{
  "error": "Missing authorization token"
}
```

### Invalid Token
**Status:** 400 Bad Request
```json
{
  "error": "Invalid token or token expired"
}
```

### Duplicate Email
**Status:** 409 Conflict
```json
{
  "error": "Email already exists"
}
```

### Missing Fields
**Status:** 400 Bad Request
```json
{
  "error": "Missing required fields"
}
```

---

## Notes

- JWT tokens expire after 24 hours
- All requests require `Content-Type: application/json`
- Authorization header format: `Bearer <token>`
- Use `-UseBasicParsing` flag to avoid PowerShell parsing issues
- Database is SQLite at `marketplace.db` in project root

---

## Next Steps

- [ ] Test all authentication endpoints
- [ ] Implement listings endpoints (POST, GET, UPDATE, DELETE)
- [ ] Implement task requests endpoints
- [ ] Implement reviews system
- [ ] Add error handling and validation
- [ ] Create integration tests
