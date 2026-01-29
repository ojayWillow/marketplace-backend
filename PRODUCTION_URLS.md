# Production Deployment URLs

## 🌐 Backend URL

**Railway Production**: `https://marketplace-backend-production-e808.up.railway.app`

### API Endpoints:
- Health Check: `https://marketplace-backend-production-e808.up.railway.app/api/health`
- Socket.IO: `https://marketplace-backend-production-e808.up.railway.app/socket.io/`
- Auth: `https://marketplace-backend-production-e808.up.railway.app/api/auth/`
- Users: `https://marketplace-backend-production-e808.up.railway.app/api/users/`
- Listings: `https://marketplace-backend-production-e808.up.railway.app/api/listings/`
- Messages: `https://marketplace-backend-production-e808.up.railway.app/api/conversations/`

---

## 🧪 Testing Your Backend

### 1. Test Health Endpoint

```bash
curl https://marketplace-backend-production-e808.up.railway.app/api/health
```

**Expected Response**:
```json
{"status": "healthy"}
```

### 2. Test Socket.IO Connection

```bash
curl https://marketplace-backend-production-e808.up.railway.app/socket.io/?transport=polling
```

**Expected Response**:
```
0{"sid":"abc123...","upgrades":["websocket"],"pingInterval":25000,"pingTimeout":20000,"maxPayload":1000000}
```

### 3. Test CORS (from browser console)

```javascript
fetch('https://marketplace-backend-production-e808.up.railway.app/api/health')
  .then(r => r.json())
  .then(d => console.log(d))
  .catch(e => console.error('CORS Error:', e));
```

---

## 📱 Frontend Configuration

### Mobile App (React Native / Expo)

**File**: `marketplace-frontend/apps/mobile/.env.local`

```bash
# Railway Production Backend
EXPO_PUBLIC_API_URL=https://marketplace-backend-production-e808.up.railway.app/api
```

**Or in** `app.config.js`:

```javascript
export default {
  name: 'Marketplace',
  slug: 'marketplace',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL || 'https://marketplace-backend-production-e808.up.railway.app/api',
  },
  // ... rest of config
};
```

### Web App (Next.js / React)

**File**: `marketplace-frontend/apps/web/.env.production`

```bash
NEXT_PUBLIC_API_URL=https://marketplace-backend-production-e808.up.railway.app/api
```

---

## 🔄 Update Backend CORS

In Railway, make sure `FRONTEND_URL` matches your actual frontend URL:

```bash
# If frontend is on Vercel
FRONTEND_URL=https://marketplace-frontend-tau-seven.vercel.app

# If frontend is also on Railway
FRONTEND_URL=https://your-frontend.up.railway.app

# For local development (add to CORS allowed origins in Flask app)
# You may need to update Flask-CORS config to include localhost
```

---

## 🔐 Test Authentication Flow

### 1. Register a Test User

```bash
curl -X POST https://marketplace-backend-production-e808.up.railway.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "username": "testuser",
    "full_name": "Test User"
  }'
```

**Expected Response**:
```json
{
  "message": "Registration successful",
  "user": {...},
  "access_token": "eyJ..."
}
```

### 2. Login

```bash
curl -X POST https://marketplace-backend-production-e808.up.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'
```

### 3. Test Protected Endpoint

```bash
TOKEN="your-access-token-from-login"

curl https://marketplace-backend-production-e808.up.railway.app/api/users/me \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔍 Troubleshooting

### Issue: "Cannot reach backend"

**Check Railway Logs**:
```bash
railway logs --follow
```

**Verify service is running**:
- Railway Dashboard → marketplace-backend → Should show "Online"
- Check deployment logs for errors

### Issue: "CORS Error"

**Solution 1**: Update `FRONTEND_URL` in Railway
```bash
FRONTEND_URL=https://your-actual-frontend-url.com
```

**Solution 2**: Check Flask CORS configuration

File: `app/__init__.py`

Ensure CORS is configured for your frontend:
```python
CORS(app, 
     resources={r"/api/*": {"origins": os.getenv('FRONTEND_URL')}},
     supports_credentials=True)
```

### Issue: "Socket.IO not connecting"

**Check**:
1. Backend URL doesn't end with `/api` for Socket.IO
2. Frontend Socket.IO client config:
   ```javascript
   const socket = io('https://marketplace-backend-production-e808.up.railway.app', {
     transports: ['websocket', 'polling'],
   });
   ```

### Issue: "502 Bad Gateway"

**Causes**:
- App not listening on `$PORT` (Railway injects this)
- App crashed or failed to start
- Migrations failed

**Check Logs**:
```bash
railway logs --tail 100
```

Look for:
- `Starting gunicorn on port 8080`
- `[INFO] Listening at: http://0.0.0.0:8080`

---

## 📊 Monitoring

### Check Deployment Status:
- Railway Dashboard → marketplace-backend → Deployments
- View logs for errors
- Monitor resource usage (CPU, Memory)

### Key Metrics:
- **Response Time**: < 200ms for API calls
- **Memory Usage**: Should stay under 512MB
- **Active Socket.IO Connections**: Monitor in logs

---

## 🚀 Deploy Frontend to Railway (Optional)

### If you want to deploy frontend to Railway too:

1. Create new Railway project
2. Connect `marketplace-frontend` repo
3. Railway will auto-detect (or use custom Dockerfile)
4. Set environment variables:
   ```bash
   EXPO_PUBLIC_API_URL=https://marketplace-backend-production-e808.up.railway.app/api
   ```
5. Generate domain for frontend
6. Update backend `FRONTEND_URL` to match

---

## 📋 Checklist

- [x] Backend deployed on Railway
- [x] PostgreSQL database connected
- [x] Environment variables configured
- [x] Migrations completed
- [x] Backend URL: `marketplace-backend-production-e808.up.railway.app`
- [ ] Test `/api/health` endpoint
- [ ] Test Socket.IO connection
- [ ] Update frontend `.env` with backend URL
- [ ] Update backend `FRONTEND_URL` with actual frontend URL
- [ ] Test authentication flow
- [ ] Test Socket.IO presence tracking
- [ ] Test file uploads (Cloudinary)
- [ ] Test push notifications

---

## 🆘 Support

**Railway Docs**: https://docs.railway.app
**Flask-SocketIO**: https://flask-socketio.readthedocs.io
**Your Project**: https://github.com/ojayWillow/marketplace-backend
