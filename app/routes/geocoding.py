"""Geocoding proxy routes.

Proxies requests to OpenStreetMap Nominatim so the browser doesn't
hit CORS errors when calling the API directly.
"""

import requests
from flask import Blueprint, jsonify, request

geocoding_bp = Blueprint('geocoding', __name__)

NOMINATIM_BASE = 'https://nominatim.openstreetmap.org'
HEADERS = {'User-Agent': 'Kolab-Marketplace/1.0 (https://kolab.lv)'}


@geocoding_bp.route('/geocode', methods=['GET'])
def geocode():
    """Forward geocode: address → lat/lon."""
    q = request.args.get('q', '')
    if not q:
        return jsonify({'error': 'Missing query parameter q'}), 400

    params = {
        'q': q,
        'format': 'json',
        'addressdetails': '1',
        'limit': request.args.get('limit', '5'),
        'countrycodes': request.args.get('countrycodes', 'lv'),
    }

    try:
        resp = requests.get(f'{NOMINATIM_BASE}/search', params=params,
                            headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json()), 200
    except requests.RequestException as e:
        return jsonify({'error': f'Geocoding failed: {e}'}), 502


@geocoding_bp.route('/reverse-geocode', methods=['GET'])
def reverse_geocode():
    """Reverse geocode: lat/lon → address."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({'error': 'Missing lat or lon parameter'}), 400

    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'addressdetails': '1',
    }

    try:
        resp = requests.get(f'{NOMINATIM_BASE}/reverse', params=params,
                            headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json()), 200
    except requests.RequestException as e:
        return jsonify({'error': f'Reverse geocoding failed: {e}'}), 502
