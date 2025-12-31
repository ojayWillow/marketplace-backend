"""Listing routes for classifieds buy/sell marketplace."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Listing, User
from datetime import datetime

listings_bp = Blueprint('listings', __name__)


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
def create_listing():
    """Create a new listing."""
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['title', 'description', 'category', 'price', 'seller_id']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        listing = Listing(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            subcategory=data.get('subcategory'),
            price=data['price'],
            seller_id=data['seller_id'],
            location=data.get('location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude')
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
def update_listing(listing_id):
    """Update an existing listing."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
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
def delete_listing(listing_id):
    """Delete a listing."""
    try:
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        db.session.delete(listing)
        db.session.commit()
        
        return jsonify({'message': 'Listing deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
