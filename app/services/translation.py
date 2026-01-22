"""Translation service with caching and swappable providers."""
import os
import hashlib
import requests
import logging

logger = logging.getLogger(__name__)

# Configuration - change this to switch providers
TRANSLATION_SERVICE = os.environ.get('TRANSLATION_SERVICE', 'google')
GOOGLE_API_KEY = os.environ.get('GOOGLE_TRANSLATE_API_KEY', '')

# Supported languages
SUPPORTED_LANGUAGES = ['lv', 'en', 'ru']

# Cache the enabled check to avoid repeated env lookups
_translation_enabled = None


def is_translation_enabled() -> bool:
    """Check if translation is properly configured. Result is cached."""
    global _translation_enabled
    
    if _translation_enabled is not None:
        return _translation_enabled
    
    if TRANSLATION_SERVICE == 'google':
        _translation_enabled = bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())
    elif TRANSLATION_SERVICE == 'deepl':
        _translation_enabled = bool(os.environ.get('DEEPL_API_KEY', '').strip())
    else:
        _translation_enabled = False
    
    return _translation_enabled


def get_text_hash(text: str) -> str:
    """Generate a hash for the text to use as cache key."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]  # Shorter hash is fine


def get_cached_translation(text: str, target_lang: str) -> str | None:
    """Check if we have a cached translation."""
    try:
        from app.models import TranslationCache
        text_hash = get_text_hash(text)
        cached = TranslationCache.query.filter_by(
            text_hash=text_hash,
            target_lang=target_lang
        ).first()
        return cached.translated_text if cached else None
    except Exception as e:
        logger.debug(f"Cache lookup error: {e}")
        return None


def cache_translation(text: str, source_lang: str, target_lang: str, translated_text: str):
    """Store a translation in the cache."""
    try:
        from app.models import TranslationCache
        from app import db
        
        # Check if already cached (race condition prevention)
        text_hash = get_text_hash(text)
        existing = TranslationCache.query.filter_by(
            text_hash=text_hash,
            target_lang=target_lang
        ).first()
        
        if existing:
            return  # Already cached
        
        cache_entry = TranslationCache(
            text_hash=text_hash,
            source_lang=source_lang,
            target_lang=target_lang,
            original_text=text[:500],  # Limit stored original text
            translated_text=translated_text
        )
        db.session.add(cache_entry)
        db.session.commit()
    except Exception as e:
        logger.debug(f"Cache storage error: {e}")
        try:
            from app import db
            db.session.rollback()
        except:
            pass


def google_translate(text: str, target_lang: str) -> tuple[str, str]:
    """Translate using Google Cloud Translation API."""
    if not GOOGLE_API_KEY:
        return text, 'unknown'
    
    url = 'https://translation.googleapis.com/language/translate/v2'
    params = {
        'key': GOOGLE_API_KEY,
        'q': text,
        'target': target_lang,
    }
    
    try:
        # Reduced timeout from 5s to 2s - fail fast
        response = requests.post(url, data=params, timeout=2)
        result = response.json()
        
        if 'data' in result and 'translations' in result['data']:
            translation = result['data']['translations'][0]
            translated_text = translation['translatedText']
            detected_lang = translation.get('detectedSourceLanguage', 'unknown')
            return translated_text, detected_lang
        else:
            logger.warning(f"Google Translate unexpected response: {result}")
    except requests.Timeout:
        logger.warning("Google Translate timeout")
    except Exception as e:
        logger.warning(f"Google Translate error: {e}")
    
    return text, 'unknown'


def deepl_translate(text: str, target_lang: str) -> tuple[str, str]:
    """Translate using DeepL API."""
    deepl_key = os.environ.get('DEEPL_API_KEY', '')
    if not deepl_key:
        return text, 'unknown'
    
    # DeepL uses uppercase language codes
    target = target_lang.upper()
    if target == 'EN':
        target = 'EN-US'
    
    url = 'https://api-free.deepl.com/v2/translate'
    headers = {'Authorization': f'DeepL-Auth-Key {deepl_key}'}
    data = {
        'text': [text],
        'target_lang': target,
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=2)
        result = response.json()
        
        if 'translations' in result:
            translation = result['translations'][0]
            return translation['text'], translation.get('detected_source_language', 'unknown').lower()
    except requests.Timeout:
        logger.warning("DeepL timeout")
    except Exception as e:
        logger.warning(f"DeepL error: {e}")
    
    return text, 'unknown'


def translate_text(text: str, target_lang: str) -> str:
    """
    Translate text to target language with caching.
    
    FAST PATHS (no API call):
    - Empty text
    - Translation disabled (no API key)
    - Cached translation exists
    
    Args:
        text: Text to translate
        target_lang: Target language code (lv, en, ru)
    
    Returns:
        Translated text (or original if translation fails/skipped)
    """
    # Fast path 1: Empty text
    if not text or not text.strip():
        return text
    
    # Fast path 2: Translation disabled entirely
    if not is_translation_enabled():
        return text
    
    # Normalize language code
    target_lang = target_lang.lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = 'en'
    
    # Fast path 3: Check cache first
    cached = get_cached_translation(text, target_lang)
    if cached:
        return cached
    
    # Translate using configured service
    if TRANSLATION_SERVICE == 'google':
        translated, source_lang = google_translate(text, target_lang)
    elif TRANSLATION_SERVICE == 'deepl':
        translated, source_lang = deepl_translate(text, target_lang)
    else:
        return text
    
    # Cache successful translations
    # Don't cache if translation failed (returned original) or same language detected
    if translated != text and source_lang != target_lang and source_lang != 'unknown':
        cache_translation(text, source_lang, target_lang, translated)
    
    return translated


def translate_task(task_dict: dict, target_lang: str) -> dict:
    """Translate task title and description."""
    if not target_lang:
        return task_dict
    
    # Fast path: if translation is disabled, return immediately
    if not is_translation_enabled():
        return task_dict
    
    title = task_dict.get('title', '')
    description = task_dict.get('description', '')
    
    if title:
        task_dict['title'] = translate_text(title, target_lang)
    if description:
        task_dict['description'] = translate_text(description, target_lang)
    
    return task_dict


def translate_offering(offering_dict: dict, target_lang: str) -> dict:
    """Translate offering title and description."""
    if not target_lang:
        return offering_dict
    
    # Fast path: if translation is disabled, return immediately
    if not is_translation_enabled():
        return offering_dict
    
    title = offering_dict.get('title', '')
    description = offering_dict.get('description', '')
    
    if title:
        offering_dict['title'] = translate_text(title, target_lang)
    if description:
        offering_dict['description'] = translate_text(description, target_lang)
    
    return offering_dict
