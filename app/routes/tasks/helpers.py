"""Shared helper functions for task routes."""

from math import radians, sin, cos, sqrt, atan2
from app.models import TaskApplication


def get_bounding_box(lat, lng, radius_km):
    """
    Calculate a bounding box for SQL filtering.
    Returns (min_lat, max_lat, min_lng, max_lng).
    """
    # Approximate degrees per km at this latitude
    lat_delta = radius_km / 111.0  # ~111 km per degree latitude
    lng_delta = radius_km / (111.0 * cos(radians(lat)))  # Adjust for longitude
    
    return (
        lat - lat_delta,  # min_lat
        lat + lat_delta,  # max_lat
        lng - lng_delta,  # min_lng
        lng + lng_delta   # max_lng
    )


def distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates using Haversine formula."""
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def translate_task_if_needed(task_dict: dict, lang: str | None) -> dict:
    """Translate task title and description if language is specified."""
    if not lang:
        return task_dict
    
    try:
        from app.services.translation import translate_task
        return translate_task(task_dict, lang)
    except Exception as e:
        # If translation fails, return original
        print(f"Translation error: {e}")
        return task_dict


def get_pending_applications_count(task_id: int) -> int:
    """Get count of pending applications for a task."""
    try:
        return TaskApplication.query.filter_by(
            task_id=task_id,
            status='pending'
        ).count()
    except Exception:
        return 0
