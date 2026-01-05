"""Helpers routes - for listing users available to help with tasks."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Review, TaskRequest
from sqlalchemy import func, and_
import math

helpers_bp = Blueprint('helpers', __name__)


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula (in km)."""
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


@helpers_bp.route('', methods=['GET'])
def get_helpers():
    """Get list of users available to help with tasks.
    
    Query params:
    - latitude: User's latitude for distance calculation
    - longitude: User's longitude for distance calculation
    - radius: Search radius in km (default: 50)
    - category: Filter by skill category
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20)
    """
    try:
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 50, type=float)
        category = request.args.get('category')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Get users who have:
        # 1. is_helper = True OR
        # 2. Have completed at least one task (they've helped before)
        # 3. Are active users
        
        # Subquery to count completed tasks for each user
        completed_tasks_subq = db.session.query(
            TaskRequest.assigned_to_id,
            func.count(TaskRequest.id).label('completed_count')
        ).filter(
            TaskRequest.status == 'completed'
        ).group_by(TaskRequest.assigned_to_id).subquery()
        
        # Query users
        query = db.session.query(
            User,
            func.coalesce(completed_tasks_subq.c.completed_count, 0).label('completed_tasks')
        ).outerjoin(
            completed_tasks_subq,
            User.id == completed_tasks_subq.c.assigned_to_id
        ).filter(
            User.is_active == True
        )
        
        # Filter: only users who have is_helper=True OR have completed at least 1 task
        query = query.filter(
            db.or_(
                User.is_helper == True,
                completed_tasks_subq.c.completed_count > 0
            )
        )
        
        # Execute query
        results = query.all()
        
        helpers = []
        for user, completed_count in results:
            # Calculate average rating
            reviews = Review.query.filter_by(reviewed_user_id=user.id).all()
            avg_rating = 0
            if reviews:
                avg_rating = sum(r.rating for r in reviews) / len(reviews)
            
            # Calculate distance if coordinates provided
            distance = None
            if latitude and longitude and user.latitude and user.longitude:
                distance = calculate_distance(latitude, longitude, user.latitude, user.longitude)
                
                # Skip if outside radius
                if distance > radius:
                    continue
            
            helper_data = {
                'id': user.id,
                'name': user.username,
                'email': user.email,  # Only public if user allows
                'avatar': user.avatar_url or user.profile_picture_url,
                'bio': user.bio,
                'city': user.city,
                'latitude': user.latitude,
                'longitude': user.longitude,
                'rating': round(avg_rating, 1),
                'review_count': len(reviews),
                'completed_tasks': completed_count or 0,
                'skills': user.skills.split(',') if user.skills else [],
                'categories': user.helper_categories.split(',') if user.helper_categories else [],
                'hourly_rate': user.hourly_rate,
                'is_available': user.is_helper,
                'member_since': user.created_at.isoformat() if user.created_at else None,
                'distance': round(distance, 1) if distance is not None else None
            }
            
            helpers.append(helper_data)
        
        # Sort by distance if coordinates provided, otherwise by rating
        if latitude and longitude:
            helpers.sort(key=lambda h: (h['distance'] if h['distance'] is not None else float('inf'), -h['rating']))
        else:
            helpers.sort(key=lambda h: (-h['rating'], -h['completed_tasks']))
        
        # Paginate
        total = len(helpers)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_helpers = helpers[start:end]
        
        return jsonify({
            'helpers': paginated_helpers,
            'total': total,
            'page': page,
            'per_page': per_page,
            'has_more': end < total
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
