"""Translation service with caching and swappable providers."""
import os
import hashlib
import requests
from app import db

# Configuration - change this to switch providers
TRANSLATION_SERVICE = os.environ.get('TRANSLATION_SERVICE', 'google')
GOOGLE_API_KEY = os.environ.get('GOOGLE_TRANSLATE_API_KEY', '')

# Supported languages
SUPPORTED_LANGUAGES = ['lv', 'en', 'ru']


class TranslationCache(db.Model):
    """Cache translations to avoid re-translating the same text."""
    __tablename__ = 'translation_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    text_hash = db.Column(db.String(64), nullable=False, index=True)
    source_lang = db.Column(db.String(5), nullable=False)
    target_lang = db.Column(db.String(5), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    __table_args__ = (
        db.UniqueConstraint('text_hash', 'target_lang', name='unique_translation'),
    )


def get_text_hash(text: str) -> str:
    """Generate a hash for the text to use as cache key."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def get_cached_translation(text: str, target_lang: str) -> str | None:
    """Check if we have a cached translation."""
    text_hash = get_text_hash(text)
    cached = TranslationCache.query.filter_by(
        text_hash=text_hash,
        target_lang=target_lang
    ).first()
    return cached.translated_text if cached else None


def cache_translation(text: str, source_lang: str, target_lang: str, translated_text: str):
    """Store a translation in the cache."""
    try:
        cache_entry = TranslationCache(
            text_hash=get_text_hash(text),
            source_lang=source_lang,
            target_lang=target_lang,
            original_text=text,
            translated_text=translated_text
        )
        db.session.add(cache_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def google_translate(text: str, target_lang: str) -> tuple[str, str]:
    """Translate using Google Cloud Translation API."""
    if not GOOGLE_API_KEY:
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
    except Exception as e:
        print(f"Google Translate error: {e}")
    
    return text, 'en'


def deepl_translate(text: str, target_lang: str) -> tuple[str, str]:
    """Translate using DeepL API (for future use)."""
    deepl_key = os.environ.get('DEEPL_API_KEY', '')
    if not deepl_key:
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
    
    # Don't cache if translation failed (returned original)
    if translated != text:
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
