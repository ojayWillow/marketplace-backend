"""Favorites routes for managing user's saved items."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Favorite, TaskRequest, Offering, Listing, User
from datetime import datetime
from functools import wraps
import jwt
import os

favorites_bp = Blueprint('favorites', __name__)

# Use same secret key as auth.py
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')


def token_required(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            request.current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated


def get_item_details(item_type, item_id):
    """Get full details for a favorited item."""
    if item_type == 'task':
        item = TaskRequest.query.get(item_id)
        if item:
            creator = User.query.get(item.creator_id)
            return {
                'id': item.id,
                'type': 'task',
                'title': item.title,
                'description': item.description,
                'category': item.category,
                'budget': float(item.budget) if item.budget else None,
                'location': item.location,
                'status': item.status,
                'is_urgent': item.is_urgent,
                'deadline': item.deadline.isoformat() if item.deadline else None,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'creator_name': creator.username if creator else 'Unknown',
                'creator_id': item.creator_id
            }
    
    elif item_type == 'offering':
        item = Offering.query.get(item_id)
        if item:
            creator = User.query.get(item.creator_id)
            return {
                'id': item.id,
                'type': 'offering',
                'title': item.title,
                'description': item.description,
                'category': item.category,
                'price': float(item.price) if item.price else None,
                'price_type': item.price_type,
                'location': item.location,
                'status': item.status,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'creator_name': creator.username if creator else 'Unknown',
                'creator_id': item.creator_id,
                'creator_avatar': creator.profile_picture_url if creator else None
            }
    
    elif item_type == 'listing':
        item = Listing.query.get(item_id)
        if item:
            seller = User.query.get(item.user_id)
            return {
                'id': item.id,
                'type': 'listing',
                'title': item.title,
                'description': item.description,
                'category': item.category,
                'price': float(item.price) if item.price else None,
                'location': item.location,
                'images': item.images,
                'status': item.status,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'seller_name': seller.username if seller else 'Unknown',
                'seller_id': item.user_id
            }
    
    return None


@favorites_bp.route('/api/favorites', methods=['POST'])
@token_required
def toggle_favorite():
    """Toggle favorite status for an item (add if not favorited, remove if already favorited)."""
    user_id = request.current_user_id
    data = request.get_json()
    
    item_type = data.get('item_type')
    item_id = data.get('item_id')
    
    if not item_type or not item_id:
        return jsonify({'error': 'item_type and item_id are required'}), 400
    
    if item_type not in ['task', 'offering', 'listing']:
        return jsonify({'error': 'Invalid item_type. Must be task, offering, or listing'}), 400
    
    # Verify item exists
    item_details = get_item_details(item_type, item_id)
    if not item_details:
        return jsonify({'error': f'{item_type.capitalize()} not found'}), 404
    
    # Toggle favorite
    is_favorited, favorite = Favorite.toggle_favorite(user_id, item_type, item_id)
    
    return jsonify({
        'is_favorited': is_favorited,
        'message': 'Added to favorites' if is_favorited else 'Removed from favorites',
        'favorite': favorite.to_dict() if favorite else None
    }), 200


@favorites_bp.route('/api/favorites', methods=['GET'])
@token_required
def get_favorites():
    """Get all favorites for the current user with full item details."""
    user_id = request.current_user_id
    item_type = request.args.get('type')  # Optional filter
    
    favorites = Favorite.get_user_favorites(user_id, item_type)
    
    result = []
    for fav in favorites:
        item_details = get_item_details(fav.item_type, fav.item_id)
        if item_details:  # Only include if item still exists
            result.append({
                'favorite_id': fav.id,
                'favorited_at': fav.created_at.isoformat() if fav.created_at else None,
                'item': item_details
            })
    
    return jsonify({
        'favorites': result,
        'total': len(result)
    }), 200


@favorites_bp.route('/api/favorites/check', methods=['GET'])
@token_required
def check_favorites():
    """Check if multiple items are favorited by the current user.
    
    Query params:
    - items: comma-separated list of "type:id" pairs, e.g., "task:1,offering:2,listing:3"
    """
    user_id = request.current_user_id
    items_param = request.args.get('items', '')
    
    if not items_param:
        return jsonify({'error': 'items parameter is required'}), 400
    
    result = {}
    for item_str in items_param.split(','):
        try:
            item_type, item_id = item_str.strip().split(':')
            item_id = int(item_id)
            key = f"{item_type}:{item_id}"
            result[key] = Favorite.is_favorited(user_id, item_type, item_id)
        except (ValueError, AttributeError):
            continue
    
    return jsonify({'favorites': result}), 200


@favorites_bp.route('/api/favorites/<int:favorite_id>', methods=['DELETE'])
@token_required
def remove_favorite(favorite_id):
    """Remove a specific favorite by its ID."""
    user_id = request.current_user_id
    
    favorite = Favorite.query.filter_by(id=favorite_id, user_id=user_id).first()
    
    if not favorite:
        return jsonify({'error': 'Favorite not found'}), 404
    
    db.session.delete(favorite)
    db.session.commit()
    
    return jsonify({'message': 'Favorite removed successfully'}), 200


@favorites_bp.route('/api/favorites/item/<item_type>/<int:item_id>', methods=['DELETE'])
@token_required
def remove_favorite_by_item(item_type, item_id):
    """Remove a favorite by item type and ID."""
    user_id = request.current_user_id
    
    if item_type not in ['task', 'offering', 'listing']:
        return jsonify({'error': 'Invalid item_type'}), 400
    
    favorite = Favorite.query.filter_by(
        user_id=user_id,
        item_type=item_type,
        item_id=item_id
    ).first()
    
    if not favorite:
        return jsonify({'error': 'Favorite not found'}), 404
    
    db.session.delete(favorite)
    db.session.commit()
    
    return jsonify({'message': 'Favorite removed successfully'}), 200


@favorites_bp.route('/api/favorites/count', methods=['GET'])
@token_required
def get_favorites_count():
    """Get count of user's favorites by type."""
    user_id = request.current_user_id
    
    total = Favorite.query.filter_by(user_id=user_id).count()
    tasks = Favorite.query.filter_by(user_id=user_id, item_type='task').count()
    offerings = Favorite.query.filter_by(user_id=user_id, item_type='offering').count()
    listings = Favorite.query.filter_by(user_id=user_id, item_type='listing').count()
    
    return jsonify({
        'total': total,
        'tasks': tasks,
        'offerings': offerings,
        'listings': listings
    }), 200
