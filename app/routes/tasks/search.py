"""Task search functionality with multilingual support and fuzzy matching."""

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
import unicodedata
import re

logger = logging.getLogger(__name__)


# Latvian diacritics mapping for normalization
LATVIAN_DIACRITICS = {
    'ā': 'a', 'č': 'c', 'ē': 'e', 'ģ': 'g', 'ī': 'i', 
    'ķ': 'k', 'ļ': 'l', 'ņ': 'n', 'š': 's', 'ū': 'u', 
    'ž': 'z', 'ō': 'o',
    # Uppercase versions
    'Ā': 'a', 'Č': 'c', 'Ē': 'e', 'Ģ': 'g', 'Ī': 'i',
    'Ķ': 'k', 'Ļ': 'l', 'Ņ': 'n', 'Š': 's', 'Ū': 'u',
    'Ž': 'z', 'Ō': 'o',
}


def normalize_latvian(text: str) -> str:
    """Normalize Latvian text by removing diacritics.
    
    Converts: tīrīt → tirit, sniegu → sniegu, ābolā → abola
    """
    if not text:
        return ''
    
    result = text.lower()
    for latvian_char, ascii_char in LATVIAN_DIACRITICS.items():
        result = result.replace(latvian_char, ascii_char)
    
    return result


def get_word_stem(word: str, min_stem_length: int = 4) -> str:
    """Get the stem of a word for fuzzy matching.
    
    For Latvian, we take the first N characters as a simple stem.
    This helps match: sniegs, sniegu, sniegā, sniegam → snieg
    
    Args:
        word: The word to stem
        min_stem_length: Minimum characters to use as stem (default 4)
    
    Returns:
        The word stem, or the full word if shorter than min_stem_length
    """
    if len(word) <= min_stem_length:
        return word
    
    # For longer words, use first N chars as stem
    # But ensure we have at least min_stem_length
    stem_length = max(min_stem_length, len(word) - 2)
    return word[:stem_length]


def create_search_patterns(search_query: str) -> list:
    """Create multiple search patterns for fuzzy matching.
    
    For each word, creates patterns for:
    1. Original word (exact match)
    2. Normalized word (without diacritics)  
    3. Word stem (for grammatical variations)
    
    Returns list of unique patterns to search for.
    """
    patterns = set()
    
    # Split into words, minimum 2 characters
    words = [w.strip().lower() for w in search_query.split() if len(w.strip()) >= 2]
    
    if not words:
        words = [search_query.lower()]
    
    for word in words:
        # 1. Original word
        patterns.add(word)
        
        # 2. Normalized (no diacritics)
        normalized = normalize_latvian(word)
        patterns.add(normalized)
        
        # 3. Word stem for both original and normalized
        if len(word) >= 4:
            patterns.add(get_word_stem(word))
            patterns.add(get_word_stem(normalized))
    
    return list(patterns)


@tasks_bp.route('/search', methods=['GET'])
def search_tasks():
    """Search for tasks with fuzzy matching and Latvian language support.
    
    Features:
    - Case-insensitive search
    - Diacritic-insensitive (tirit finds tīrīt)
    - Stem matching (sniegs finds sniegu)
    - Searches in title and description
    - Finds tasks matching ANY search pattern
    
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
        
        # Create fuzzy search patterns
        search_patterns = create_search_patterns(search_query)
        logger.info(f'Search patterns: {search_patterns}')
        
        # Build base query
        query = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # Get all tasks matching status/category first (we'll filter in Python for fuzzy matching)
        all_candidate_tasks = query.order_by(TaskRequest.created_at.desc()).all()
        logger.info(f'Found {len(all_candidate_tasks)} candidate tasks')
        
        # Fuzzy match in Python for better Latvian support
        matching_tasks = []
        for task in all_candidate_tasks:
            # Normalize task title and description
            title_normalized = normalize_latvian(task.title or '')
            desc_normalized = normalize_latvian(task.description or '')
            combined_text = f'{title_normalized} {desc_normalized}'
            
            # Check if any search pattern matches
            matched = False
            for pattern in search_patterns:
                if pattern in combined_text:
                    matched = True
                    break
            
            if matched:
                matching_tasks.append(task)
        
        logger.info(f'Found {len(matching_tasks)} matching tasks after fuzzy search')
        
        # Apply location filtering if requested
        if latitude is not None and longitude is not None:
            min_lat, max_lat, min_lng, max_lng = get_bounding_box(latitude, longitude, radius)
            
            tasks_with_distance = []
            for task in matching_tasks:
                if task.latitude is None or task.longitude is None:
                    continue
                if not (min_lat <= task.latitude <= max_lat and min_lng <= task.longitude <= max_lng):
                    continue
                    
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
            # No location filter
            tasks_list = []
            for task in matching_tasks:
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
