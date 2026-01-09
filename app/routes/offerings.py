"""Routes for service offerings."""

from flask import Blueprint, request, jsonify, g
from functools import wraps
import jwt
import os
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

from app import db
from app.models.offering import Offering
from app.models.user import User
from app.models.message import Conversation, Message

offerings_bp = Blueprint('offerings', __name__)


def token_required(f):
    """Decorator to require JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            secret_key = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key')
            data = jwt.decode(token, secret_key, algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
            g.current_user = current_user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated


def token_optional(f):
    """Decorator for optional JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        g.current_user = None
        if token:
            try:
                secret_key = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key')
                data = jwt.decode(token, secret_key, algorithms=['HS256'])
                current_user = User.query.get(data['user_id'])
                g.current_user = current_user
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                pass
        
        return f(*args, **kwargs)
    return decorated


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points on Earth using Haversine formula."""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


@offerings_bp.route('', methods=['GET'])
@token_optional
def get_offerings():
    """Get all offerings with optional filtering and geolocation."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'active')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 25, type=float)  # Default 25km
        boosted_only = request.args.get('boosted_only', 'false').lower() == 'true'
        
        query = Offering.query
        
        # Filter by status
        if status:
            query = query.filter(Offering.status == status)
        
        # Filter by category
        if category:
            query = query.filter(Offering.category == category)
        
        # Filter by boosted only (for map display)
        if boosted_only:
            # Only return offerings that are boosted AND boost hasn't expired
            query = query.filter(
                Offering.is_boosted == True,
                Offering.boost_expires_at > datetime.utcnow()
            )
        
        # Order: boosted first, then by newest
        query = query.order_by(
            Offering.is_boosted.desc(),
            Offering.created_at.desc()
        )
        
        # Execute query
        offerings = query.all()
        
        # Filter by distance if coordinates provided
        if latitude is not None and longitude is not None:
            filtered_offerings = []
            for offering in offerings:
                distance = haversine_distance(
                    latitude, longitude,
                    offering.latitude, offering.longitude
                )
                if distance <= radius:
                    offering_dict = offering.to_dict()
                    offering_dict['distance'] = round(distance, 2)
                    filtered_offerings.append(offering_dict)
            
            # Sort: boosted first, then by distance
            filtered_offerings.sort(key=lambda x: (not x.get('is_boost_active', False), x['distance']))
            
            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            paginated = filtered_offerings[start:end]
            
            return jsonify({
                'offerings': paginated,
                'total': len(filtered_offerings),
                'page': page
            }), 200
        else:
            # Paginate without distance filter
            paginated = query.paginate(page=page, per_page=per_page, error_out=False)
            
            return jsonify({
                'offerings': [o.to_dict() for o in paginated.items],
                'total': paginated.total,
                'page': page
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/my', methods=['GET'])
@token_required
def get_my_offerings():
    """Get offerings created by current user."""
    try:
        offerings = Offering.query.filter_by(creator_id=g.current_user.id).order_by(Offering.created_at.desc()).all()
        
        return jsonify({
            'offerings': [o.to_dict() for o in offerings],
            'total': len(offerings),
            'page': 1
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>', methods=['GET'])
@token_optional
def get_offering(offering_id):
    """Get a single offering by ID."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        return jsonify(offering.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('', methods=['POST'])
@token_required
def create_offering():
    """Create a new offering."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'description', 'category', 'location', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        offering = Offering(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            location=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            price=data.get('price'),
            price_type=data.get('price_type', 'hourly'),
            currency=data.get('currency', 'EUR'),
            status='active',
            creator_id=g.current_user.id,
            availability=data.get('availability'),
            experience=data.get('experience'),
            service_radius=data.get('service_radius', 25.0),
            images=data.get('images')
        )
        
        db.session.add(offering)
        db.session.commit()
        
        return jsonify({
            'message': 'Offering created successfully',
            'offering': offering.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>', methods=['PUT'])
@token_required
def update_offering(offering_id):
    """Update an existing offering."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        # Check ownership
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Update fields if provided
        updateable_fields = [
            'title', 'description', 'category', 'location', 'latitude', 'longitude',
            'price', 'price_type', 'currency', 'availability', 'experience',
            'service_radius', 'images'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(offering, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Offering updated successfully',
            'offering': offering.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>', methods=['DELETE'])
@token_required
def delete_offering(offering_id):
    """Delete an offering."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        # Check ownership
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(offering)
        db.session.commit()
        
        return jsonify({'message': 'Offering deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>/pause', methods=['POST'])
@token_required
def pause_offering(offering_id):
    """Pause an offering (temporarily hide it)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        # Check ownership
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        offering.status = 'paused'
        db.session.commit()
        
        return jsonify({
            'message': 'Offering paused',
            'offering': offering.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>/activate', methods=['POST'])
@token_required
def activate_offering(offering_id):
    """Activate/resume an offering (without boost)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        # Check ownership
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        offering.status = 'active'
        db.session.commit()
        
        return jsonify({
            'message': 'Offering activated',
            'offering': offering.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>/boost', methods=['POST'])
@token_required
def boost_offering(offering_id):
    """Boost an offering to show on the map (24-hour trial)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        # Check ownership
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json() or {}
        duration_hours = data.get('duration_hours', 24)  # Default 24 hours
        
        # For now, limit to 24 hours for free trial
        # In the future, this can be extended with payment integration
        max_free_hours = 24
        duration_hours = min(duration_hours, max_free_hours)
        
        # Activate boost
        offering.status = 'active'  # Also ensure status is active
        offering.is_boosted = True
        offering.boost_expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Offering boosted for {duration_hours} hours! It will now appear on the map.',
            'offering': offering.to_dict(),
            'boost_duration_hours': duration_hours,
            'boost_expires_at': offering.boost_expires_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>/contact', methods=['POST'])
@token_required
def contact_offering_creator(offering_id):
    """Contact the offering creator (start a conversation)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        # Can't contact yourself
        if offering.creator_id == g.current_user.id:
            return jsonify({'error': 'Cannot contact yourself'}), 400
        
        data = request.get_json()
        message_content = data.get('message', f"Hi! I'm interested in your offering: {offering.title}")
        
        # Check for existing conversation
        existing_conv = Conversation.query.filter(
            ((Conversation.participant_1_id == g.current_user.id) & (Conversation.participant_2_id == offering.creator_id)) |
            ((Conversation.participant_1_id == offering.creator_id) & (Conversation.participant_2_id == g.current_user.id))
        ).first()
        
        if existing_conv:
            conversation = existing_conv
        else:
            # Create new conversation
            conversation = Conversation(
                participant_1_id=g.current_user.id,
                participant_2_id=offering.creator_id,
                offering_id=offering.id
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Create message
        message = Message(
            conversation_id=conversation.id,
            sender_id=g.current_user.id,
            content=message_content
        )
        db.session.add(message)
        
        # Increment contact count
        offering.contact_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Message sent successfully',
            'conversation_id': conversation.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
