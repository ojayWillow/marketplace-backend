# Two-Factor Authentication (2FA) Setup Guide

## Overview

The marketplace now supports TOTP-based two-factor authentication using apps like:
- Google Authenticator
- Authy
- Microsoft Authenticator
- 1Password
- Bitwarden

---

## How It Works

### Setup Flow
```
1. User calls POST /api/auth/2fa/setup
   ↓
2. Server returns QR code + secret
   ↓
3. User scans QR with authenticator app
   ↓
4. User calls POST /api/auth/2fa/enable with 6-digit code
   ↓
5. Server verifies code and enables 2FA
   ↓
6. User receives backup codes (save these!)
```

### Login Flow (with 2FA enabled)
```
1. User calls POST /api/auth/login with email + password
   ↓
2. Server returns partial_token + requires_2fa: true
   ↓
3. User calls POST /api/auth/2fa/verify with partial_token + code
   ↓
4. Server verifies code and returns full access token
```

---

## API Endpoints

### Setup 2FA
```http
POST /api/auth/2fa/setup
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Scan QR code with your authenticator app",
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,...",
  "provisioning_uri": "otpauth://totp/Marketplace:user@email.com?secret=..."
}
```

### Enable 2FA
```http
POST /api/auth/2fa/enable
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "123456"
}
```

**Response:**
```json
{
  "message": "2FA enabled successfully",
  "backup_codes": ["A1B2C3D4", "E5F6G7H8", ...],
  "warning": "Save these backup codes! They can only be viewed once."
}
```

### Verify 2FA (during login)
```http
POST /api/auth/2fa/verify
Content-Type: application/json

{
  "partial_token": "<token from login response>",
  "code": "123456"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "token": "<full access token>",
  "user": { ... }
}
```

### Disable 2FA
```http
POST /api/auth/2fa/disable
Authorization: Bearer <token>
Content-Type: application/json

{
  "password": "your_password",
  "code": "123456"
}
```

### Get 2FA Status
```http
GET /api/auth/2fa/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "totp_enabled": true,
  "backup_codes_remaining": 6
}
```

### Regenerate Backup Codes
```http
POST /api/auth/2fa/backup-codes
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "123456"
}
```

---

## Backup Codes

- 8 backup codes generated when 2FA is enabled
- Each code can only be used once
- Use if you lose access to your authenticator app
- Format: 8-character alphanumeric (e.g., "A1B2C3D4")
- Can regenerate codes anytime (invalidates old ones)

---

## Testing with cURL

### 1. Login and get token
```bash
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | jq -r '.token')
```

### 2. Setup 2FA
```bash
curl -X POST http://localhost:5000/api/auth/2fa/setup \
  -H "Authorization: Bearer $TOKEN" \
  | jq
```

### 3. Enable 2FA (use code from authenticator)
```bash
curl -X POST http://localhost:5000/api/auth/2fa/enable \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code":"123456"}'
```

### 4. Test login with 2FA
```bash
# First login (get partial token)
RESPONSE=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}')

PARTIAL_TOKEN=$(echo $RESPONSE | jq -r '.partial_token')

# Verify with 2FA code
curl -X POST http://localhost:5000/api/auth/2fa/verify \
  -H "Content-Type: application/json" \
  -d "{\"partial_token\":\"$PARTIAL_TOKEN\",\"code\":\"123456\"}"
```

---

## Frontend Integration Notes

### Login Flow Changes

```typescript
const login = async (email: string, password: string) => {
  const response = await api.post('/auth/login', { email, password });
  
  if (response.data.requires_2fa) {
    // Show 2FA verification screen
    return {
      requires2FA: true,
      partialToken: response.data.partial_token
    };
  }
  
  // Normal login - store token
  setToken(response.data.token);
  return { success: true };
};

const verify2FA = async (partialToken: string, code: string) => {
  const response = await api.post('/auth/2fa/verify', {
    partial_token: partialToken,
    code
  });
  
  setToken(response.data.token);
  return { success: true };
};
```

### QR Code Display

```tsx
const TwoFactorSetup = () => {
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  
  const setup2FA = async () => {
    const response = await api.post('/auth/2fa/setup');
    setQrCode(response.data.qr_code);
    setSecret(response.data.secret);
  };
  
  return (
    <div>
      <img src={qrCode} alt="Scan with authenticator app" />
      <p>Or enter manually: {secret}</p>
      <input placeholder="Enter 6-digit code" />
    </div>
  );
};
```

---

## Security Considerations

1. **Backup codes** are hashed/stored securely
2. **Partial tokens** expire in 10 minutes
3. **TOTP window** allows ±30 seconds tolerance
4. **Password required** to disable 2FA
5. **Secrets** are stored encrypted (consider adding encryption at rest)

---

## Database Changes

New fields added to `users` table:

| Field | Type | Description |
|-------|------|-------------|
| `totp_secret` | VARCHAR(32) | Base32 encoded secret |
| `totp_enabled` | BOOLEAN | Whether 2FA is active |
| `totp_backup_codes` | TEXT | Comma-separated backup codes |

**Note**: Run database migration or recreate tables to add new fields.

```bash
# If using Flask-Migrate
flask db migrate -m "Add TOTP 2FA fields"
flask db upgrade

# Or for SQLite development (delete and recreate)
rm marketplace.db
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```
