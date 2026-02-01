"""Vonage SMS Verification Service for phone number authentication.

This service handles sending and verifying OTP codes via Vonage SMS API.
Replaces Twilio due to Latvia region restrictions on trial accounts.

Updated to use Vonage Python SDK v4 API structure.
"""

import os
import secrets
import time
from flask import current_app

# Vonage SDK v4 imports
from vonage import Vonage, Auth
from vonage_sms import SmsMessage, SmsResponse

# Vonage credentials from environment variables
VONAGE_API_KEY = os.environ.get('VONAGE_API_KEY')
VONAGE_API_SECRET = os.environ.get('VONAGE_API_SECRET')

# In-memory OTP storage (in production, use Redis with TTL)
# Format: {phone_number: {'code': '123456', 'expires': timestamp, 'attempts': 0}}
_otp_storage = {}
OTP_EXPIRY_SECONDS = 300  # 5 minutes
MAX_VERIFY_ATTEMPTS = 3

# Rate limiting storage
_otp_attempts = {}  # phone -> {'count': int, 'first_attempt': timestamp}
MAX_OTP_REQUESTS_PER_HOUR = 5
OTP_COOLDOWN_SECONDS = 60  # Minimum seconds between requests


def _get_vonage_client():
    """Get configured Vonage client instance.
    
    Returns:
        Vonage: Configured Vonage client
        
    Raises:
        ValueError: If credentials not configured
    """
    if not VONAGE_API_KEY or not VONAGE_API_SECRET:
        raise ValueError(
            "Vonage credentials not configured. "
            "Set VONAGE_API_KEY and VONAGE_API_SECRET environment variables."
        )
    
    auth = Auth(api_key=VONAGE_API_KEY, api_secret=VONAGE_API_SECRET)
    return Vonage(auth=auth)


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


def check_rate_limit(phone: str) -> tuple:
    """Check if phone number has exceeded rate limit.
    
    Args:
        phone: Normalized phone number
        
    Returns:
        Tuple of (is_allowed, error_message)
    """
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
    current_time = time.time()
    
    if phone in _otp_attempts:
        _otp_attempts[phone]['count'] += 1
        _otp_attempts[phone]['last_attempt'] = current_time
    else:
        _otp_attempts[phone] = {
            'count': 1,
            'first_attempt': current_time,
            'last_attempt': current_time
        }


def generate_otp_code() -> str:
    """Generate a 6-digit OTP code."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])


def send_verification_code(phone: str) -> dict:
    """Send OTP verification code to phone number via Vonage SMS API.
    
    Args:
        phone: Phone number to send verification code to
        
    Returns:
        dict with 'success' boolean and 'message' or 'error'
        
    Raises:
        ValueError: If phone number is invalid or Vonage not configured
    """
    normalized_phone = normalize_phone_number(phone)
    
    if not normalized_phone or len(normalized_phone) < 10:
        return {'success': False, 'error': 'Invalid phone number format'}
    
    # Check rate limit
    is_allowed, error_msg = check_rate_limit(normalized_phone)
    if not is_allowed:
        return {'success': False, 'error': error_msg}
    
    try:
        # Get Vonage client (validates credentials)
        vonage_client = _get_vonage_client()
        
        # Generate OTP code
        otp_code = generate_otp_code()
        
        # Store OTP with expiry
        _otp_storage[normalized_phone] = {
            'code': otp_code,
            'expires': time.time() + OTP_EXPIRY_SECONDS,
            'attempts': 0
        }
        
        # Prepare phone number for Vonage (without + prefix)
        to_number = normalized_phone.lstrip('+')
        
        # Create SMS message using Vonage SDK v4
        message = SmsMessage(
            to=to_number,
            from_='Tirgus',
            text=f'Your Tirgus verification code is: {otp_code}. Valid for 5 minutes.'
        )
        
        # Send SMS via Vonage SDK
        response: SmsResponse = vonage_client.sms.send(message)
        
        # Check response - SDK v4 returns SmsResponse object
        # Check if any message was successful
        if response.messages and len(response.messages) > 0:
            first_message = response.messages[0]
            if first_message.status == '0':
                # Success - record attempt for rate limiting
                record_otp_attempt(normalized_phone)
                
                current_app.logger.info(f"OTP sent to {normalized_phone} via Vonage")
                
                return {
                    'success': True,
                    'message': 'Verification code sent',
                    'phone': normalized_phone,
                }
            else:
                # Failed - get error text
                error_text = getattr(first_message, 'error_text', 'Unknown error')
                current_app.logger.error(
                    f"Vonage error sending OTP to {normalized_phone}: {error_text}"
                )
                return {'success': False, 'error': f'Failed to send SMS: {error_text}'}
        else:
            current_app.logger.error(
                f"Vonage returned empty response for {normalized_phone}"
            )
            return {'success': False, 'error': 'Failed to send SMS: Empty response'}
        
    except ValueError as e:
        current_app.logger.error(f"Vonage configuration error: {e}")
        raise
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
    normalized_phone = normalize_phone_number(phone)
    
    if not normalized_phone:
        return {'success': False, 'error': 'Invalid phone number'}
    
    if not code or len(code) < 4:
        return {'success': False, 'error': 'Invalid verification code'}
    
    # Check if we have stored OTP for this phone
    stored_otp = _otp_storage.get(normalized_phone)
    
    if not stored_otp:
        return {'success': False, 'error': 'No verification code found. Please request a new one.'}
    
    # Check if expired
    if time.time() > stored_otp['expires']:
        del _otp_storage[normalized_phone]
        return {'success': False, 'error': 'Verification code expired. Please request a new one.'}
    
    # Check attempt limit
    if stored_otp['attempts'] >= MAX_VERIFY_ATTEMPTS:
        del _otp_storage[normalized_phone]
        return {'success': False, 'error': 'Too many incorrect attempts. Please request a new code.'}
    
    # Increment attempts
    stored_otp['attempts'] += 1
    
    # Verify code
    if stored_otp['code'] == code:
        # Success - remove from storage
        del _otp_storage[normalized_phone]
        
        current_app.logger.info(f"OTP verified successfully for {normalized_phone}")
        
        return {
            'success': True,
            'message': 'Phone number verified',
            'phone': normalized_phone,
        }
    else:
        remaining = MAX_VERIFY_ATTEMPTS - stored_otp['attempts']
        current_app.logger.warning(
            f"Invalid OTP attempt for {normalized_phone}, {remaining} attempts remaining"
        )
        
        return {
            'success': False,
            'error': f'Invalid verification code. {remaining} attempts remaining.',
        }
