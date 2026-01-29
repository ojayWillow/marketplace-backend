# Railway Deployment Guide

## ✅ What I've Fixed

### Commits Made:
1. **[85c3d9e](https://github.com/ojayWillow/marketplace-backend/commit/85c3d9e3667506ef04232a866027365afcab47e2)** - Fixed debug mode security vulnerability
2. **[34e32ed](https://github.com/ojayWillow/marketplace-backend/commit/34e32ed1e7e75df9415c084e3cf0ed1db520168b)** - Switched from development server to Gunicorn
3. **[7b7c9ac](https://github.com/ojayWillow/marketplace-backend/commit/7b7c9ac4ac3136f1ce2e77ad33c3a6fa4dbc83a4)** - Added Railway configuration

### Security Fixes:
- ❌ **BEFORE**: `debug=True` hardcoded (DANGEROUS!)
- ✅ **AFTER**: Debug mode controlled by environment variable
- ❌ **BEFORE**: Using Werkzeug development server
- ✅ **AFTER**: Using Gunicorn with gevent workers (production-ready)

---

## 🚀 Railway Setup Steps

### Step 1: Railway will Auto-Deploy

Since Railway is already active, it will automatically detect the new commits and redeploy.

Watch the deployment logs in Railway dashboard:
```
Settings → Deployments → View Logs
```

You should see:
```bash
[MIGRATION] Running database migrations...
[MIGRATION] Completed
Starting gunicorn on port 5000...
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:5000
```

### Step 2: Configure Environment Variables

Go to Railway Dashboard → Your Service → **Variables** tab:

#### Required Variables:
```bash
# Database (should already exist)
DATABASE_URL=postgresql://...

# Security
JWT_SECRET=your-secret-here-min-32-chars
FLASK_ENV=production
FLASK_DEBUG=0

# Cloudinary (for image uploads)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Frontend URL (update after deploying frontend)
FRONTEND_URL=https://your-frontend.up.railway.app

# Push Notifications (VAPID keys - generate these)
VAPID_PUBLIC_KEY=your-vapid-public-key
VAPID_PRIVATE_KEY=your-vapid-private-key

# Python config
PYTHONUNBUFFERED=1
```

#### Optional Variables:
```bash
# Email (if using email features)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### Step 3: Generate VAPID Keys for Push Notifications

Run this locally to generate keys:

```bash
cd marketplace-backend
python3 << 'EOF'
from py_vapid import Vapid

vapid = Vapid()
vapid.generate_keys()

print("\n=== Copy these to Railway Variables ===")
print(f"VAPID_PUBLIC_KEY={vapid.public_key.savePublicKey().decode()}")
print(f"VAPID_PRIVATE_KEY={vapid.private_key.savePrivateKey().decode()}")
print("\n")
EOF
```

### Step 4: Verify Deployment

After Railway redeploys, check:

1. **Health Check**: Visit `https://your-app.up.railway.app/api/health`
   - Should return: `{"status": "healthy"}`

2. **Check Logs** for these confirmations:
   ```
   ✅ [MIGRATION] Completed
   ✅ Starting gunicorn on port XXX
   ✅ [PUSH] VAPID_PUBLIC_KEY configured: True
   ❌ WARNING: * Debugger is active! (should NOT appear)
   ```

3. **Test Socket.IO**: 
   ```bash
   curl https://your-app.up.railway.app/socket.io/?transport=polling
   ```
   Should return: `0{"sid":"..."}`

---

## 🗄️ Database Setup

### Option 1: Railway PostgreSQL (Recommended)

1. In Railway dashboard, click **"+ New"** → **"Database"** → **"PostgreSQL"
2. Railway auto-generates `DATABASE_URL`
3. Migrations run automatically on deploy (via `start.sh`)

### Option 2: External Database (e.g., Neon, Supabase)

If using external Postgres:
1. Create database on your provider
2. Get connection string
3. Set `DATABASE_URL` in Railway variables

---

## 🌐 Custom Domain (Optional)

### Add Custom Domain:
1. Railway Dashboard → Settings → **Domains**
2. Click **"+ Add Domain"**
3. Enter your domain: `api.yourdomain.com`
4. Add CNAME record to your DNS:
   ```
   CNAME  api  your-app.up.railway.app
   ```

---

## 📊 Monitoring & Logs

### View Live Logs:
```bash
# Via CLI
railway logs --follow

# Or in Dashboard
Deployments → View Logs
```

### Key Metrics to Watch:
- **Memory Usage**: Should stay under 512MB
- **Response Time**: < 200ms for API calls
- **Socket.IO Connections**: Monitor active connections
- **Database Connections**: Should not exceed pool limit

---

## 🔧 Troubleshooting

### Issue: "Address already in use"
**Solution**: Railway injects `$PORT` - ensure you're using it:
```python
port = int(os.getenv('PORT', 5000))
```

### Issue: Database migrations fail
**Solution**: Check DATABASE_URL is set correctly
```bash
railway run python run_migration.py
```

### Issue: Socket.IO not working
**Check**:
1. Gunicorn using `gevent` worker class
2. CORS configured for frontend domain
3. WebSocket transport enabled

### Issue: "Module not found" errors
**Solution**: Rebuild with fresh dependencies
```bash
railway up --detach
```

---

## 🚀 Frontend Setup (Next Step)

### Update Frontend Environment Variables:

**File**: `marketplace-frontend/apps/mobile/.env` (or Expo config)

```bash
EXPO_PUBLIC_API_URL=https://your-backend.up.railway.app/api
```

**File**: `marketplace-frontend/apps/web/.env` (if using web)

```bash
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app/api
```

### Deploy Frontend to Railway:

1. Create new Railway project
2. Connect `marketplace-frontend` repo
3. Railway will detect Dockerfile or use Nixpacks
4. Set environment variables
5. Deploy!

---

## 📋 Post-Deployment Checklist

- [ ] Backend deployed and healthy
- [ ] Database connected and migrations run
- [ ] Environment variables configured
- [ ] VAPID keys generated and added
- [ ] Debug mode DISABLED (`FLASK_DEBUG=0`)
- [ ] Gunicorn running (not Werkzeug)
- [ ] Socket.IO working
- [ ] Frontend URL updated in backend CORS
- [ ] Backend URL updated in frontend config
- [ ] Custom domain configured (optional)
- [ ] Push notifications tested
- [ ] File uploads working (Cloudinary)

---

## 💰 Railway Pricing

**Free Tier**:
- $5 credit/month
- ~500 hours of uptime
- Perfect for testing

**Hobby Plan** ($5/month):
- Unlimited uptime
- Custom domains
- Better support

**Pro Plan** ($20/month):
- Teams
- More resources
- Priority support

---

## 🆘 Support

If you encounter issues:
1. Check Railway logs first
2. Review environment variables
3. Test API endpoints manually
4. Check this guide's troubleshooting section

**Railway Docs**: https://docs.railway.app
