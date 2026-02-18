"""Shared helper utilities for route handlers."""

import math
from flask import jsonify
import logging

logger = logging.getLogger(__name__)

# Price / budget limits — single source of truth
MIN_PRICE = 10
MAX_PRICE = 10000


def validate_price_range(value, field_name='Price'):
    """Validate that a price/budget value is a number between MIN_PRICE and MAX_PRICE.
    
    Args:
        value: The value to validate (can be str, int, float, or None)
        field_name: Human-readable name for error messages (e.g. 'Price', 'Budget')
    
    Returns:
        A Flask JSON error response tuple (jsonify, status_code) if validation fails,
        or None if the value is valid.
    
    Usage:
        error_response = validate_price_range(data.get('budget'), 'Budget')
        if error_response:
            return error_response
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return jsonify({'error': f'{field_name} must be a valid number'}), 400
    
    # Reject NaN, Infinity, -Infinity
    if not math.isfinite(num):
        return jsonify({'error': f'{field_name} must be a valid number'}), 400
    
    if num < MIN_PRICE or num > MAX_PRICE:
        return jsonify({'error': f'{field_name} must be between \u20ac{MIN_PRICE} and \u20ac{MAX_PRICE:,}'}), 400
    
    return None
