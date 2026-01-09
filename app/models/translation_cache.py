"""Translation cache model for storing translated content."""
from app import db


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
