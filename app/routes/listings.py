"""Listing routes for classifieds buy/sell marketplace."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Listing, User
from app.utils import token_required
from datetime import datetime

listings_bp = Blueprint('listings', __name__)


# Fields that can be set when creating/updating a listing
UPDATEABLE_FIELDS = [
    'title', 'description', 'category', 'subcategory', 'price',
    'location', 'latitude', 'longitude', 'images', 'contact_info',
    'condition', 'is_negotiable', 'status'
]


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
        
        query = query.order_by(Listing.created_at.desc())
        
        listings = query.paginate(page=page, per_page=per_page)
        
        return jsonify([listing.to_dict() for listing in listings.items]), 200
    except Exception:
        raise


@listings_bp.route('/my', methods=['GET'])
@token_required
def get_my_listings(current_user_id):
    """Get authenticated user's own listings."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        
        query = Listing.query.filter_by(seller_id=current_user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        query = query.order_by(Listing.created_at.desc())
        
        listings = query.paginate(page=page, per_page=per_page)
        
        return jsonify({
            'listings': [listing.to_dict() for listing in listings.items],
            'total': listings.total,
            'pages': listings.pages,
            'current_page': page
        }), 200
    except Exception:
        raise


@listings_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_listings(user_id):
    """Get active listings by a specific user (public endpoint for profile view)."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = Listing.query.filter_by(
            seller_id=user_id,
            status='active'
        ).order_by(Listing.created_at.desc())
        
        listings = query.paginate(page=page, per_page=per_page)
        
        return jsonify({
            'listings': [listing.to_dict() for listing in listings.items],
            'total': listings.total,
            'pages': listings.pages,
            'current_page': page
        }), 200
    except Exception:
        raise


@listings_bp.route('/<int:listing_id>', methods=['GET'])
def get_listing(listing_id):
    """Get a specific listing by ID with seller details."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        listing.views_count += 1
        db.session.commit()
        
        return jsonify(listing.to_dict(include_seller_details=True)), 200
    except Exception:
        raise


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
            contact_info=data.get('contact_info'),
            condition=data.get('condition'),
            is_negotiable=data.get('is_negotiable', False)
        )
        
        db.session.add(listing)
        db.session.commit()
        
        return jsonify({
            'message': 'Listing created successfully',
            'listing': listing.to_dict()
        }), 201
    except Exception:
        db.session.rollback()
        raise


@listings_bp.route('/<int:listing_id>', methods=['PUT'])
@token_required
def update_listing(current_user_id, listing_id):
    """Update an existing listing.
    
    Uses an explicit allowlist of fields to prevent attackers from
    setting protected attributes like views_count or seller_id.
    """
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        if listing.seller_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Allowlist: only these fields can be updated
        for field in UPDATEABLE_FIELDS:
            if field in data:
                setattr(listing, field, data[field])
        
        listing.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Listing updated successfully',
            'listing': listing.to_dict()
        }), 200
    except Exception:
        db.session.rollback()
        raise


@listings_bp.route('/<int:listing_id>', methods=['DELETE'])
@token_required
def delete_listing(current_user_id, listing_id):
    """Delete a listing."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        if listing.seller_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(listing)
        db.session.commit()
        
        return jsonify({'message': 'Listing deleted successfully'}), 200
    except Exception:
        db.session.rollback()
        raise
