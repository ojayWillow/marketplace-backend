"""Task search functionality with multilingual support."""

from flask import request, jsonify
from sqlalchemy import or_, func, and_
from sqlalchemy.orm import joinedload
from app import db
from app.models import TaskRequest, TranslationCache
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
    """Search for tasks with multilingual support and fuzzy matching.
    
    Searches across:
    - Original title and description (splits words, handles grammar)
    - All translations in translation cache
    
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
        
        logger.info(f'Searching tasks with query: "{search_query}", lang: {lang}')
        
        # Build base query with eager loading
        query = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # IMPROVED: Split query into words to handle grammar variations
        # "tīrīt sniegu" -> ["tīrīt", "sniegu"]
        # Will match "Sniega tīrīšana" because it contains "snieg" stem
        search_words = [word.strip().lower() for word in search_query.split() if len(word.strip()) >= 3]
        
        if not search_words:
            # If query too short or no valid words, fallback to exact match
            search_words = [search_query.lower()]
        
        logger.info(f'Search words: {search_words}')
        
        # Find task IDs that match ANY of the search words
        all_matching_ids = set()
        task_match_counts = {}  # Track how many words matched per task (for ranking)
        
        for word in search_words:
            word_pattern = f'%{word}%'
            
            # Step 1: Find tasks matching in original title/description
            original_matches = db.session.query(TaskRequest.id).filter(
                or_(
                    func.lower(TaskRequest.title).like(word_pattern),
                    func.lower(TaskRequest.description).like(word_pattern)
                )
            ).all()
            
            for (task_id,) in original_matches:
                all_matching_ids.add(task_id)
                task_match_counts[task_id] = task_match_counts.get(task_id, 0) + 1
            
            # Step 2: Find task IDs that match in translation cache
            translation_matches = db.session.query(
                TranslationCache.original_text
            ).filter(
                func.lower(TranslationCache.translated_text).like(word_pattern)
            ).all()
            
            # Find tasks with those original texts
            for (original_text,) in translation_matches:
                matching_tasks = db.session.query(TaskRequest.id).filter(
                    or_(
                        TaskRequest.title == original_text,
                        TaskRequest.description == original_text
                    )
                ).all()
                
                for (task_id,) in matching_tasks:
                    all_matching_ids.add(task_id)
                    task_match_counts[task_id] = task_match_counts.get(task_id, 0) + 1
        
        all_matching_ids = list(all_matching_ids)
        
        logger.info(f'Found {len(all_matching_ids)} tasks matching search')
        
        # If no matches, return empty result
        if not all_matching_ids:
            return jsonify({
                'tasks': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'has_more': False
            }), 200
        
        # Apply ID filter to main query
        query = query.filter(TaskRequest.id.in_(all_matching_ids))
        
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
            
            # Filter by exact distance
            tasks_with_distance = []
            for task in all_tasks:
                dist = distance(latitude, longitude, task.latitude, task.longitude)
                if dist <= radius:
                    task_dict = task.to_dict()
                    task_dict['distance'] = round(dist, 2)
                    task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
                    task_dict['match_score'] = task_match_counts.get(task.id, 1)  # Relevance score
                    task_dict = translate_task_if_needed(task_dict, lang)
                    tasks_with_distance.append(task_dict)
            
            # Sort by relevance (match_score) first, then distance
            tasks_with_distance.sort(key=lambda x: (-x['match_score'], x['distance']))
            
            total = len(tasks_with_distance)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = tasks_with_distance[start:end]
            
            return jsonify({
                'tasks': paginated_results,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': end < total
            }), 200
        else:
            # No location filter - order by relevance, then created_at
            all_tasks = query.all()
            
            tasks_list = []
            for task in all_tasks:
                task_dict = translate_task_if_needed(task.to_dict(), lang)
                task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
                task_dict['match_score'] = task_match_counts.get(task.id, 1)
                tasks_list.append(task_dict)
            
            # Sort by relevance
            tasks_list.sort(key=lambda x: -x['match_score'])
            
            total = len(tasks_list)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = tasks_list[start:end]
            
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
