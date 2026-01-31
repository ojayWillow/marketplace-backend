"""Twilio SMS Verification Service for phone number authentication.

This service handles sending and verifying OTP codes via Twilio Verify API.
Works with Expo Go without any native modules.
"""

import os
from flask import current_app
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Twilio credentials from environment variables
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_VERIFY_SERVICE_SID = os.environ.get('TWILIO_VERIFY_SERVICE_SID')

# Rate limiting storage (in production, use Redis)
_otp_attempts = {}  # phone -> {'count': int, 'first_attempt': timestamp}
MAX_OTP_REQUESTS_PER_HOUR = 5
OTP_COOLDOWN_SECONDS = 60  # Minimum seconds between requests


def get_twilio_client():
    """Get Twilio client instance."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        raise ValueError("Twilio credentials not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables.")
    
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to E.164 format.
    
    Args:
        phone: Phone number in any format
        
    Returns:
        Phone number in E.164 format (e.g., '+37120000000')
    """
    if not phone:
        return None
    
    # Remove all non-digit characters except leading +
    cleaned = ''.join(c for c in phone if c.isdigit() or (c == '+' and phone.index(c) == 0))
    
    # Ensure it starts with +
    if not cleaned.startswith('+'):
        # Assume Latvian number if no country code
        if len(cleaned) == 8:
            cleaned = '+371' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned


def check_rate_limit(phone: str) -> tuple[bool, str]:
    """Check if phone number has exceeded rate limit.
    
    Args:
        phone: Normalized phone number
        
    Returns:
        Tuple of (is_allowed, error_message)
    """
    import time
    
    current_time = time.time()
    
    if phone in _otp_attempts:
        attempts = _otp_attempts[phone]
        time_since_first = current_time - attempts['first_attempt']
        time_since_last = current_time - attempts.get('last_attempt', 0)
        
        # Reset if more than an hour has passed
        if time_since_first > 3600:
            _otp_attempts[phone] = {
                'count': 0,
                'first_attempt': current_time,
                'last_attempt': current_time
            }
        # Check cooldown between requests
        elif time_since_last < OTP_COOLDOWN_SECONDS:
            wait_time = int(OTP_COOLDOWN_SECONDS - time_since_last)
            return False, f"Please wait {wait_time} seconds before requesting another code"
        # Check max attempts per hour
        elif attempts['count'] >= MAX_OTP_REQUESTS_PER_HOUR:
            return False, "Too many verification attempts. Please try again later."
    else:
        _otp_attempts[phone] = {
            'count': 0,
            'first_attempt': current_time,
            'last_attempt': current_time
        }
    
    return True, None


def record_otp_attempt(phone: str):
    """Record an OTP attempt for rate limiting."""
    import time
    
    if phone in _otp_attempts:
        _otp_attempts[phone]['count'] += 1
        _otp_attempts[phone]['last_attempt'] = time.time()
    else:
        _otp_attempts[phone] = {
            'count': 1,
            'first_attempt': time.time(),
            'last_attempt': time.time()
        }


def send_verification_code(phone: str) -> dict:
    """Send OTP verification code to phone number via Twilio Verify.
    
    Args:
        phone: Phone number to send verification code to
        
    Returns:
        dict with 'success' boolean and 'message' or 'error'
        
    Raises:
        ValueError: If phone number is invalid or Twilio not configured
    """
    if not TWILIO_VERIFY_SERVICE_SID:
        raise ValueError("Twilio Verify Service SID not configured. Set TWILIO_VERIFY_SERVICE_SID environment variable.")
    
    normalized_phone = normalize_phone_number(phone)
    
    if not normalized_phone or len(normalized_phone) < 10:
        return {'success': False, 'error': 'Invalid phone number format'}
    
    # Check rate limit
    is_allowed, error_msg = check_rate_limit(normalized_phone)
    if not is_allowed:
        return {'success': False, 'error': error_msg}
    
    try:
        client = get_twilio_client()
        
        verification = client.verify \
            .v2 \
            .services(TWILIO_VERIFY_SERVICE_SID) \
            .verifications \
            .create(to=normalized_phone, channel='sms')
        
        # Record the attempt for rate limiting
        record_otp_attempt(normalized_phone)
        
        current_app.logger.info(f"OTP sent to {normalized_phone}, status: {verification.status}")
        
        return {
            'success': True,
            'message': 'Verification code sent',
            'phone': normalized_phone,
            'status': verification.status
        }
        
    except TwilioRestException as e:
        current_app.logger.error(f"Twilio error sending OTP to {normalized_phone}: {e}")
        
        # Handle specific Twilio errors
        if e.code == 60200:
            return {'success': False, 'error': 'Invalid phone number'}
        elif e.code == 60203:
            return {'success': False, 'error': 'Max verification attempts reached. Try again later.'}
        elif e.code == 60205:
            return {'success': False, 'error': 'SMS not supported for this phone number'}
        else:
            return {'success': False, 'error': 'Failed to send verification code. Please try again.'}
    
    except Exception as e:
        current_app.logger.error(f"Error sending OTP to {normalized_phone}: {e}")
        return {'success': False, 'error': 'Failed to send verification code'}


def verify_code(phone: str, code: str) -> dict:
    """Verify OTP code entered by user.
    
    Args:
        phone: Phone number the code was sent to
        code: The verification code entered by user
        
    Returns:
        dict with 'success' boolean and verification result or error
    """
    if not TWILIO_VERIFY_SERVICE_SID:
        raise ValueError("Twilio Verify Service SID not configured")
    
    normalized_phone = normalize_phone_number(phone)
    
    if not normalized_phone:
        return {'success': False, 'error': 'Invalid phone number'}
    
    if not code or len(code) < 4:
        return {'success': False, 'error': 'Invalid verification code'}
    
    try:
        client = get_twilio_client()
        
        verification_check = client.verify \
            .v2 \
            .services(TWILIO_VERIFY_SERVICE_SID) \
            .verification_checks \
            .create(to=normalized_phone, code=code)
        
        current_app.logger.info(f"OTP verification for {normalized_phone}: {verification_check.status}")
        
        if verification_check.status == 'approved':
            return {
                'success': True,
                'message': 'Phone number verified',
                'phone': normalized_phone,
                'status': verification_check.status
            }
        else:
            return {
                'success': False,
                'error': 'Invalid verification code',
                'status': verification_check.status
            }
        
    except TwilioRestException as e:
        current_app.logger.error(f"Twilio error verifying OTP for {normalized_phone}: {e}")
        
        if e.code == 60202:
            return {'success': False, 'error': 'Verification code expired. Request a new one.'}
        elif e.code == 60200:
            return {'success': False, 'error': 'Invalid verification code'}
        else:
            return {'success': False, 'error': 'Verification failed. Please try again.'}
    
    except Exception as e:
        current_app.logger.error(f"Error verifying OTP for {normalized_phone}: {e}")
        return {'success': False, 'error': 'Verification failed'}
