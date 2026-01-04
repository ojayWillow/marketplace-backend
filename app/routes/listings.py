"""Listing routes for classifieds buy/sell marketplace."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Listing, User
from datetime import datetime
import os
import jwt
from functools import wraps

listings_bp = Blueprint('listings', __name__)
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

@listings_bp.route('', methods=['GET'])
def get_listings():
    """Get all listings with filtering and pagination."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        category = request.args.get('category')
        status = request.args.get('status', 'active')
        
        query = Listing.query.filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # Order by newest first
        query = query.order_by(Listing.created_at.desc())
        
        listings = query.paginate(page=page, per_page=per_page)
        
        return jsonify([listing.to_dict() for listing in listings.items]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@listings_bp.route('/my', methods=['GET'])
@token_required
def get_my_listings(current_user_id):
    """Get authenticated user's own listings."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')  # Optional filter by status
        
        query = Listing.query.filter_by(seller_id=current_user_id)
        
        # Filter by status if provided, otherwise return all
        if status:
            query = query.filter_by(status=status)
        
        # Order by newest first
        query = query.order_by(Listing.created_at.desc())
        
        listings = query.paginate(page=page, per_page=per_page)
        
        return jsonify({
            'listings': [listing.to_dict() for listing in listings.items],
            'total': listings.total,
            'pages': listings.pages,
            'current_page': page
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@listings_bp.route('/<int:listing_id>', methods=['GET'])
def get_listing(listing_id):
    """Get a specific listing by ID."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        listing.views_count += 1
        db.session.commit()
        
        return jsonify(listing.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@listings_bp.route('', methods=['POST'])
@token_required
def create_listing(current_user_id):
    """Create a new listing."""
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['title', 'description', 'category', 'price']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        listing = Listing(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            subcategory=data.get('subcategory'),
            price=data['price'],
            seller_id=current_user_id,
            location=data.get('location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            images=data.get('images'),
            contact_info=data.get('contact_info')
        )
        
        db.session.add(listing)
        db.session.commit()
        
        return jsonify({
            'message': 'Listing created successfully',
            'listing': listing.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@listings_bp.route('/<int:listing_id>', methods=['PUT'])
@token_required
def update_listing(current_user_id, listing_id):
    """Update an existing listing."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        # Check ownership
        if listing.seller_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        for key, value in data.items():
            if hasattr(listing, key) and key not in ['id', 'seller_id', 'created_at']:
                setattr(listing, key, value)
        
        listing.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Listing updated successfully',
            'listing': listing.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@listings_bp.route('/<int:listing_id>', methods=['DELETE'])
@token_required
def delete_listing(current_user_id, listing_id):
    """Delete a listing."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        # Check ownership
        if listing.seller_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(listing)
        db.session.commit()
        
        return jsonify({'message': 'Listing deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
