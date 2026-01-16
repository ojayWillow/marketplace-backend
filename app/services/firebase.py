"""Firebase Authentication Service for phone number verification.

This service verifies Firebase ID tokens sent from the frontend
after users complete phone number verification via Firebase Auth.
"""

import requests
from flask import current_app
import time
import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Firebase project ID - should match your Firebase project
FIREBASE_PROJECT_ID = 'tirgus-marketplace'

# Google's public keys endpoint for verifying Firebase tokens
GOOGLE_CERTS_URL = 'https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com'
FIREBASE_ISSUER = f'https://securetoken.google.com/{FIREBASE_PROJECT_ID}'

# Cache for Google's public keys (refreshed every hour)
_cached_keys = None
_keys_fetched_at = 0
KEYS_CACHE_DURATION = 3600  # 1 hour


def get_google_public_keys():
    """Fetch Google's public keys for verifying Firebase tokens.
    
    Keys are cached for 1 hour to avoid repeated requests.
    Returns a dict mapping key ID to public key object.
    """
    global _cached_keys, _keys_fetched_at
    
    current_time = time.time()
    
    # Return cached keys if still valid
    if _cached_keys and (current_time - _keys_fetched_at) < KEYS_CACHE_DURATION:
        return _cached_keys
    
    try:
        response = requests.get(GOOGLE_CERTS_URL, timeout=10)
        response.raise_for_status()
        certs_data = response.json()
        
        # Parse X.509 certificates and extract public keys
        public_keys = {}
        for kid, cert_pem in certs_data.items():
            try:
                # Parse the X.509 certificate
                cert = x509.load_pem_x509_certificate(
                    cert_pem.encode('utf-8'),
                    default_backend()
                )
                # Extract the public key
                public_keys[kid] = cert.public_key()
            except Exception as e:
                current_app.logger.warning(f"Failed to parse certificate for kid {kid}: {e}")
                continue
        
        if not public_keys:
            raise ValueError("No valid public keys found in Google's response")
        
        _cached_keys = public_keys
        _keys_fetched_at = current_time
        return _cached_keys
        
    except Exception as e:
        current_app.logger.error(f"Failed to fetch Google public keys: {e}")
        # Return cached keys even if expired, as fallback
        if _cached_keys:
            return _cached_keys
        raise


def verify_firebase_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return the decoded claims.
    
    Args:
        id_token: The Firebase ID token from the frontend
        
    Returns:
        dict: Decoded token claims containing:
            - uid: Firebase user ID
            - phone_number: Verified phone number (e.g., '+37120000000')
            - auth_time: When the user authenticated
            
    Raises:
        ValueError: If token is invalid, expired, or verification fails
    """
    from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
    
    if not id_token:
        raise ValueError("ID token is required")
    
    try:
        # Decode the token header to get the key ID
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get('kid')
        alg = unverified_header.get('alg')
        
        if not kid:
            raise ValueError("Token missing key ID (kid)")
        
        if alg != 'RS256':
            raise ValueError(f"Unexpected algorithm: {alg}")
        
        # Get Google's public keys
        public_keys = get_google_public_keys()
        
        if kid not in public_keys:
            # Refresh keys in case of rotation
            global _keys_fetched_at
            _keys_fetched_at = 0
            public_keys = get_google_public_keys()
            
            if kid not in public_keys:
                raise ValueError(f"Token signed with unknown key: {kid}")
        
        # Get the public key for this key ID
        public_key = public_keys[kid]
        
        # Verify and decode the token
        decoded = jwt.decode(
            id_token,
            public_key,
            algorithms=['RS256'],
            audience=FIREBASE_PROJECT_ID,
            issuer=FIREBASE_ISSUER
        )
        
        # Verify required claims
        if 'phone_number' not in decoded:
            raise ValueError("Token does not contain phone number claim")
        
        if not decoded.get('sub'):
            raise ValueError("Token does not contain subject (user ID)")
        
        return {
            'uid': decoded['sub'],
            'phone_number': decoded['phone_number'],
            'auth_time': decoded.get('auth_time'),
            'firebase_user': decoded
        }
        
    except ExpiredSignatureError:
        raise ValueError("Token has expired")
    except InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Firebase token verification error: {e}")
        raise ValueError(f"Token verification failed: {str(e)}")


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
