"""Routes for service offerings."""

from flask import Blueprint, request, jsonify, g, current_app
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

from app import db
from app.models.offering import Offering
from app.models.user import User
from app.models.message import Conversation, Message
from app.utils import token_required_g, token_optional_g
from app.routes.helpers import validate_price_range
from app.constants.categories import validate_category, normalize_category

offerings_bp = Blueprint('offerings', __name__)


def get_bounding_box(lat, lng, radius_km):
    R = 6371.0
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * cos(radians(lat)))
    lat_delta *= 1.1
    lng_delta *= 1.1
    return (
        lat - lat_delta,
        lat + lat_delta,
        lng - lng_delta,
        lng + lng_delta
    )


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def translate_offering_if_needed(offering_dict: dict, lang: str | None) -> dict:
    if not lang:
        return offering_dict
    try:
        from app.services.translation import translate_offering
        return translate_offering(offering_dict, lang)
    except Exception as e:
        current_app.logger.error(f"Translation error: {e}")
        return offering_dict


def _offering_sort_key(offering_dict):
    """Sort key: promoted first, then boosted, then regular."""
    if offering_dict.get('is_promote_active'):
        return 0
    if offering_dict.get('is_boost_active'):
        return 1
    return 2


@offerings_bp.route('', methods=['GET'])
@token_optional_g
def get_offerings():
    """Get all offerings with optional filtering, geolocation, and translation.
    
    Sorting order:
        1. Promoted offerings (paid) first
        2. Boosted offerings (paid) second
        3. Regular offerings by distance or date
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'active')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 25, type=float)
        boosted_only = request.args.get('boosted_only', 'false').lower() == 'true'
        lang = request.args.get('lang')
        
        query = Offering.query
        
        if status:
            query = query.filter(Offering.status == status)
        
        if category:
            normalized = normalize_category(category)
            query = query.filter(Offering.category == normalized)
        
        if boosted_only:
            query = query.filter(
                Offering.is_boosted == True,
                Offering.boost_expires_at > datetime.utcnow()
            )
        
        if latitude is not None and longitude is not None:
            min_lat, max_lat, min_lng, max_lng = get_bounding_box(latitude, longitude, radius)
            query = query.filter(
                Offering.latitude >= min_lat,
                Offering.latitude <= max_lat,
                Offering.longitude >= min_lng,
                Offering.longitude <= max_lng
            )
        
        # Base SQL ordering: promoted → boosted → regular, then newest
        now = datetime.utcnow()
        from sqlalchemy import case as sql_case
        query = query.order_by(
            sql_case(
                (db.and_(Offering.is_promoted == True, Offering.promoted_expires_at > now), 0),
                (db.and_(Offering.is_boosted == True, Offering.boost_expires_at > now), 1),
                else_=2
            ),
            Offering.created_at.desc()
        )
        
        offerings = query.all()
        
        if latitude is not None and longitude is not None:
            filtered_offerings = []
            for offering in offerings:
                dist = haversine_distance(
                    latitude, longitude,
                    offering.latitude, offering.longitude
                )
                if dist <= radius:
                    offering_dict = offering.to_dict()
                    offering_dict['distance'] = round(dist, 2)
                    offering_dict = translate_offering_if_needed(offering_dict, lang)
                    filtered_offerings.append(offering_dict)
            
            # Sort: promoted first → boosted second → then by distance
            filtered_offerings.sort(key=lambda x: (_offering_sort_key(x), x['distance']))
            
            start = (page - 1) * per_page
            end = start + per_page
            paginated = filtered_offerings[start:end]
            
            return jsonify({
                'offerings': paginated,
                'total': len(filtered_offerings),
                'page': page
            }), 200
        else:
            paginated = query.paginate(page=page, per_page=per_page, error_out=False)
            
            offerings_list = [translate_offering_if_needed(o.to_dict(), lang) for o in paginated.items]
            
            return jsonify({
                'offerings': offerings_list,
                'total': paginated.total,
                'page': page
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/my', methods=['GET'])
@token_required_g
def get_my_offerings():
    """Get offerings created by current user."""
    try:
        lang = request.args.get('lang')
        
        offerings = Offering.query.filter_by(creator_id=g.current_user.id).order_by(Offering.created_at.desc()).all()
        
        offerings_list = [translate_offering_if_needed(o.to_dict(), lang) for o in offerings]
        
        return jsonify({
            'offerings': offerings_list,
            'total': len(offerings),
            'page': 1
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_offerings(user_id):
    """Get active offerings by a specific user (public endpoint for profile view)."""
    try:
        lang = request.args.get('lang')
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        offerings = Offering.query.filter_by(
            creator_id=user_id,
            status='active'
        ).order_by(Offering.created_at.desc()).all()
        
        offerings_list = [translate_offering_if_needed(o.to_dict(), lang) for o in offerings]
        
        return jsonify({
            'offerings': offerings_list,
            'total': len(offerings),
            'page': 1
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>', methods=['GET'])
@token_optional_g
def get_offering(offering_id):
    """Get a single offering by ID."""
    try:
        lang = request.args.get('lang')
        
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        offering_dict = translate_offering_if_needed(offering.to_dict(), lang)
        return jsonify(offering_dict), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('', methods=['POST'])
@token_required_g
def create_offering():
    """Create a new offering."""
    try:
        data = request.get_json()
        
        required_fields = ['title', 'description', 'category', 'location', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        category, cat_error = validate_category(data['category'])
        if cat_error:
            return jsonify({'error': cat_error}), 400
        
        price_type = data.get('price_type', 'hourly')
        price = data.get('price')
        if price_type != 'negotiable' and price is not None:
            error_response = validate_price_range(price, 'Price')
            if error_response:
                return error_response
        
        offering = Offering(
            title=data['title'],
            description=data['description'],
            category=category,
            location=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            price=data.get('price'),
            price_type=price_type,
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
@token_required_g
def update_offering(offering_id):
    """Update an existing offering."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        price_type = data.get('price_type', offering.price_type)
        if 'price' in data and data['price'] is not None and price_type != 'negotiable':
            error_response = validate_price_range(data['price'], 'Price')
            if error_response:
                return error_response
        
        if 'category' in data:
            category, cat_error = validate_category(data['category'])
            if cat_error:
                return jsonify({'error': cat_error}), 400
            data['category'] = category
        
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
@token_required_g
def delete_offering(offering_id):
    """Delete an offering."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        if offering.creator_id != g.current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(offering)
        db.session.commit()
        
        return jsonify({'message': 'Offering deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@offerings_bp.route('/<int:offering_id>/pause', methods=['POST'])
@token_required_g
def pause_offering(offering_id):
    """Pause an offering (temporarily hide it)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
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
@token_required_g
def activate_offering(offering_id):
    """Activate/resume an offering (without boost)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
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
@token_required_g
def boost_offering(offering_id):
    """Boost an offering — now requires payment.
    
    The free boost trial has ended. Use POST /api/payments/create-order
    with type='boost_offering' instead.
    
    Returns 410 Gone with instructions to use the payments endpoint.
    """
    return jsonify({
        'error': 'Free boost is no longer available. Please use the payments API.',
        'payment_endpoint': '/api/payments/create-order',
        'payment_type': 'boost_offering',
        'price': '€1.00',
        'duration': '24 hours'
    }), 410


@offerings_bp.route('/<int:offering_id>/contact', methods=['POST'])
@token_required_g
def contact_offering_creator(offering_id):
    """Contact the offering creator (start a conversation)."""
    try:
        offering = Offering.query.get(offering_id)
        
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        if offering.creator_id == g.current_user.id:
            return jsonify({'error': 'Cannot contact yourself'}), 400
        
        data = request.get_json()
        message_content = data.get('message', f"Hi! I'm interested in your offering: {offering.title}")
        
        existing_conv = Conversation.query.filter(
            ((Conversation.participant_1_id == g.current_user.id) & (Conversation.participant_2_id == offering.creator_id)) |
            ((Conversation.participant_1_id == offering.creator_id) & (Conversation.participant_2_id == g.current_user.id))
        ).first()
        
        if existing_conv:
            conversation = existing_conv
        else:
            conversation = Conversation(
                participant_1_id=g.current_user.id,
                participant_2_id=offering.creator_id,
                offering_id=offering.id
            )
            db.session.add(conversation)
            db.session.flush()
        
        message = Message(
            conversation_id=conversation.id,
            sender_id=g.current_user.id,
            content=message_content
        )
        db.session.add(message)
        
        offering.contact_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Message sent successfully',
            'conversation_id': conversation.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
