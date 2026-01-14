"""Translation service with caching and swappable providers."""
import os
import hashlib
import requests

# Configuration - change this to switch providers
TRANSLATION_SERVICE = os.environ.get('TRANSLATION_SERVICE', 'google')
GOOGLE_API_KEY = os.environ.get('GOOGLE_TRANSLATE_API_KEY', '')

# Supported languages
SUPPORTED_LANGUAGES = ['lv', 'en', 'ru']


def is_translation_enabled() -> bool:
    """Check if translation is properly configured."""
    if TRANSLATION_SERVICE == 'google':
        return bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())
    elif TRANSLATION_SERVICE == 'deepl':
        return bool(os.environ.get('DEEPL_API_KEY', '').strip())
    return False


def get_text_hash(text: str) -> str:
    """Generate a hash for the text to use as cache key."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


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
        print(f"Cache lookup error: {e}")
        return None


def cache_translation(text: str, source_lang: str, target_lang: str, translated_text: str):
    """Store a translation in the cache."""
    try:
        from app.models import TranslationCache
        from app import db
        cache_entry = TranslationCache(
            text_hash=get_text_hash(text),
            source_lang=source_lang,
            target_lang=target_lang,
            original_text=text,
            translated_text=translated_text
        )
        db.session.add(cache_entry)
        db.session.commit()
    except Exception as e:
        print(f"Cache storage error: {e}")
        try:
            from app import db
            db.session.rollback()
        except:
            pass


def google_translate(text: str, target_lang: str) -> tuple[str, str]:
    """Translate using Google Cloud Translation API."""
    if not GOOGLE_API_KEY:
        # No API key - return original text immediately (no network call)
        return text, 'en'
    
    url = 'https://translation.googleapis.com/language/translate/v2'
    params = {
        'key': GOOGLE_API_KEY,
        'q': text,
        'target': target_lang,
    }
    
    try:
        response = requests.post(url, data=params, timeout=5)
        result = response.json()
        
        if 'data' in result and 'translations' in result['data']:
            translation = result['data']['translations'][0]
            translated_text = translation['translatedText']
            detected_lang = translation.get('detectedSourceLanguage', 'en')
            return translated_text, detected_lang
        else:
            print(f"Google Translate unexpected response: {result}")
    except Exception as e:
        print(f"Google Translate error: {e}")
    
    return text, 'en'


def deepl_translate(text: str, target_lang: str) -> tuple[str, str]:
    """Translate using DeepL API (for future use)."""
    deepl_key = os.environ.get('DEEPL_API_KEY', '')
    if not deepl_key:
        # No API key - return original text immediately (no network call)
        return text, 'en'
    
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
        response = requests.post(url, headers=headers, data=data, timeout=5)
        result = response.json()
        
        if 'translations' in result:
            translation = result['translations'][0]
            return translation['text'], translation.get('detected_source_language', 'EN').lower()
    except Exception as e:
        print(f"DeepL error: {e}")
    
    return text, 'en'


def translate_text(text: str, target_lang: str) -> str:
    """
    Translate text to target language with caching.
    
    Args:
        text: Text to translate
        target_lang: Target language code (lv, en, ru)
    
    Returns:
        Translated text
    """
    if not text or not text.strip():
        return text
    
    # Skip translation entirely if not configured (fast path)
    if not is_translation_enabled():
        return text
    
    # Normalize language code
    target_lang = target_lang.lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = 'en'
    
    # Check cache first
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
    
    # Don't cache if translation failed (returned original) or same language
    if translated != text and source_lang != target_lang:
        cache_translation(text, source_lang, target_lang, translated)
    
    return translated


def translate_task(task_dict: dict, target_lang: str) -> dict:
    """Translate task title and description."""
    if target_lang:
        task_dict['title'] = translate_text(task_dict.get('title', ''), target_lang)
        task_dict['description'] = translate_text(task_dict.get('description', ''), target_lang)
    return task_dict


def translate_offering(offering_dict: dict, target_lang: str) -> dict:
    """Translate offering title and description."""
    if target_lang:
        offering_dict['title'] = translate_text(offering_dict.get('title', ''), target_lang)
        offering_dict['description'] = translate_text(offering_dict.get('description', ''), target_lang)
    return offering_dict
