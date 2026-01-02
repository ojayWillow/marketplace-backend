# STEP BY STEP - ONLY DO ONE STEP AT A TIME

## 👉 STEP 1: Run This First (Takes 5 minutes)

Open your terminal/PowerShell in the project folder and copy-paste this:

```bash
python -m venv venv
```

Then activate it:

**On Mac/Linux:**
```bash
source venv/bin/activate
```

**On Windows (PowerShell):**
```bash
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```bash
venv\Scripts\activate.bat
```

You should see `(venv)` at the start of your terminal line.

✅ **When done, reply: "STEP 1 DONE"**

---

## 👉 STEP 2: Install Dependencies (Takes 2 minutes)

Still in terminal with `(venv)` showing, run:

```bash
pip install -r requirements.txt
```

Wait for it to finish. It will say "Successfully installed..."

✅ **When done, reply: "STEP 2 DONE"**

---

## 👉 STEP 3: Create .env File (Takes 1 minute)

In the project root folder, create a new file called `.env`

Put this inside:

```
FLASK_APP=wsgi.py
FLASK_ENV=development
DATABASE_URL=sqlite:///test.db
JWT_SECRET_KEY=dev-secret-key-12345
```

✅ **When done, reply: "STEP 3 DONE"**

---

## 👉 STEP 4: Check Flask Works (Takes 2 minutes)

Still in terminal with `(venv)`, run:

```bash
flask run
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

DO NOT close this window. Keep it running.

✅ **When you see this message, reply: "FLASK IS RUNNING"**

---

## 👉 STEP 5: Test Health Endpoint (New Terminal)

OPEN A NEW TERMINAL WINDOW (don't close the Flask one)

Run this command:

```bash
curl http://localhost:5000/health
```

You should see:
```json
{"status":"ok"}
```

✅ **When you see this, reply: "HEALTH CHECK WORKS"**

Then we can move to the next step!

---

## ⚠️ Issues?

| Issue | Fix |
|-------|-----|
| Command not found: python | Install Python |
| Command not found: pip | Python not in PATH |
| ModuleNotFoundError | Did you activate venv? Check `(venv)` shows |
| Port 5000 already in use | Another app using port, change in wsgi.py |
| curl: command not found | You're on Windows, use PowerShell version below |

**Windows PowerShell curl alternative:**
```powershell
Invoke-WebRequest http://localhost:5000/health
```

---

---

## ✍️ STEP 6: Test User Registration (NEW - Do This Next)

Keep Flask running in the first terminal.

In the second terminal where you tested health, run this:

```bash
Invoke-WebRequest -Uri http://localhost:5000/api/auth/register -Method POST -ContentType "application/json" -Body '{"username":"testuser","email":"test@example.com","password":"testpass123","first_name":"Test","last_name":"User"}' -UseBasicParsing
```

You should see a response with status 201 and a user object.

✅ **When you see status 201 and user data, reply: "USER REGISTRATION WORKS"**

If you get an error, tell me what the error says.

---

**Great progress! The backend is alive and responding! 🚀**

**Remember: ONE STEP AT A TIME. Reply when each step is done.**
