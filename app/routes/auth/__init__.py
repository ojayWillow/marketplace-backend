"""Auth routes package.

This package organizes authentication-related routes into logical submodules:
- core: Registration, login, shared helpers and validators
- phone: Vonage OTP phone authentication (send, verify, link, check)
- phone_legacy: Deprecated Firebase phone authentication
- password: Password reset flow (forgot + reset)
- profile: User profile CRUD and public user endpoints
"""

from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

# Import all route modules (registers routes on auth_bp)
from app.routes.auth import core
from app.routes.auth import phone
from app.routes.auth import phone_legacy
from app.routes.auth import password
from app.routes.auth import profile
