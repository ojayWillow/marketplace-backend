"""Task search functionality with multilingual support."""

from flask import request, jsonify
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from app import db
from app.models import TaskRequest
from app.routes.tasks import tasks_bp
from app.routes.tasks.helpers import (
    get_bounding_box,
    distance,
    translate_task_if_needed,
    get_pending_applications_count
)
import logging

logger = logging.getLogger(__name__)


@tasks_bp.route('/search', methods=['GET'])
def search_tasks():
    """Search for tasks with fuzzy matching.
    
    Simple search that works:
    - Searches in title and description
    - Splits query into words
    - Finds tasks containing ANY of the words
    - Case-insensitive
    
    Query params:
        - q: Search query string (required)
        - lang: Language code for results translation (lv, en, ru)
        - status: Filter by status (default 'open')
        - category: Filter by category
        - latitude, longitude: User location for distance filtering
        - radius: Search radius in km (default 10)
        - page, per_page: Pagination
    """
    try:
        # Get search query
        search_query = request.args.get('q', '').strip()
        if not search_query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Get other params
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'open')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 10, type=float)
        lang = request.args.get('lang')
        
        logger.info(f'Searching tasks with query: "{search_query}", lang: {lang}, status: {status}')
        
        # Build base query
        query = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # Split search query into words (min 2 chars to catch "ts" etc)
        search_words = [word.strip().lower() for word in search_query.split() if len(word.strip()) >= 2]
        
        if not search_words:
            search_words = [search_query.lower()]
        
        logger.info(f'Search words: {search_words}')
        
        # Build OR conditions for each word
        # Each word should match in EITHER title OR description
        search_conditions = []
        for word in search_words:
            word_pattern = f'%{word}%'
            search_conditions.append(
                or_(
                    func.lower(TaskRequest.title).like(word_pattern),
                    func.lower(TaskRequest.description).like(word_pattern)
                )
            )
        
        # Combine all word conditions with OR (match ANY word)
        if search_conditions:
            query = query.filter(or_(*search_conditions))
        
        logger.info(f'Executing search query...')
        
        # If location filtering is requested
        if latitude is not None and longitude is not None:
            min_lat, max_lat, min_lng, max_lng = get_bounding_box(latitude, longitude, radius)
            query = query.filter(
                TaskRequest.latitude.isnot(None),
                TaskRequest.longitude.isnot(None),
                TaskRequest.latitude >= min_lat,
                TaskRequest.latitude <= max_lat,
                TaskRequest.longitude >= min_lng,
                TaskRequest.longitude <= max_lng
            )
            
            all_tasks = query.all()
            logger.info(f'Found {len(all_tasks)} tasks before distance filter')
            
            # Filter by exact distance
            tasks_with_distance = []
            for task in all_tasks:
                dist = distance(latitude, longitude, task.latitude, task.longitude)
                if dist <= radius:
                    task_dict = task.to_dict()
                    task_dict['distance'] = round(dist, 2)
                    task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
                    task_dict = translate_task_if_needed(task_dict, lang)
                    tasks_with_distance.append(task_dict)
            
            # Sort by distance
            tasks_with_distance.sort(key=lambda x: x['distance'])
            
            total = len(tasks_with_distance)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = tasks_with_distance[start:end]
            
            logger.info(f'Returning {len(paginated_results)} tasks (total: {total})')
            
            return jsonify({
                'tasks': paginated_results,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': end < total
            }), 200
        else:
            # No location filter - just order by created_at
            all_tasks = query.order_by(TaskRequest.created_at.desc()).all()
            logger.info(f'Found {len(all_tasks)} tasks without location filter')
            
            tasks_list = []
            for task in all_tasks:
                task_dict = translate_task_if_needed(task.to_dict(), lang)
                task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
                tasks_list.append(task_dict)
            
            total = len(tasks_list)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = tasks_list[start:end]
            
            logger.info(f'Returning {len(paginated_results)} tasks (total: {total})')
            
            return jsonify({
                'tasks': paginated_results,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': end < total
            }), 200
            
    except Exception as e:
        logger.error(f'Error searching tasks: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500
