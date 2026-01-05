"""Message routes for user-to-user communication."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Conversation, Message
from datetime import datetime
from functools import wraps
from sqlalchemy import or_, and_
import jwt
import os

messages_bp = Blueprint('messages', __name__)

# Use same secret key as auth.py
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')


def token_required(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid', 'details': str(e)}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


@messages_bp.route('/conversations', methods=['GET'])
@token_required
def get_conversations(current_user_id):
    """Get all conversations for the current user."""
    try:
        conversations = Conversation.query.filter(
            or_(
                Conversation.participant_1_id == current_user_id,
                Conversation.participant_2_id == current_user_id
            )
        ).order_by(Conversation.updated_at.desc()).all()
        
        return jsonify({
            'conversations': [conv.to_dict(current_user_id) for conv in conversations],
            'total': len(conversations)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/conversations', methods=['POST'])
@token_required
def create_conversation(current_user_id):
    """Create a new conversation or return existing one."""
    try:
        data = request.get_json()
        other_user_id = data.get('user_id')
        task_id = data.get('task_id')  # Optional: link conversation to a task
        initial_message = data.get('message')  # Optional: send first message immediately
        
        if not other_user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        if other_user_id == current_user_id:
            return jsonify({'error': 'Cannot start conversation with yourself'}), 400
        
        # Check if other user exists
        other_user = User.query.get(other_user_id)
        if not other_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if conversation already exists between these users
        existing_conversation = Conversation.query.filter(
            or_(
                and_(
                    Conversation.participant_1_id == current_user_id,
                    Conversation.participant_2_id == other_user_id
                ),
                and_(
                    Conversation.participant_1_id == other_user_id,
                    Conversation.participant_2_id == current_user_id
                )
            )
        ).first()
        
        if existing_conversation:
            # If there's an initial message, add it to existing conversation
            if initial_message:
                message = Message(
                    conversation_id=existing_conversation.id,
                    sender_id=current_user_id,
                    content=initial_message
                )
                db.session.add(message)
                existing_conversation.updated_at = datetime.utcnow()
                db.session.commit()
            
            return jsonify({
                'conversation': existing_conversation.to_dict(current_user_id),
                'existing': True
            }), 200
        
        # Create new conversation
        conversation = Conversation(
            participant_1_id=current_user_id,
            participant_2_id=other_user_id,
            task_id=task_id
        )
        
        db.session.add(conversation)
        db.session.flush()  # Get the conversation ID
        
        # Add initial message if provided
        if initial_message:
            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user_id,
                content=initial_message
            )
            db.session.add(message)
        
        db.session.commit()
        
        return jsonify({
            'conversation': conversation.to_dict(current_user_id),
            'existing': False
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/conversations/<int:conversation_id>', methods=['GET'])
@token_required
def get_conversation(current_user_id, conversation_id):
    """Get a specific conversation."""
    try:
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is a participant
        if current_user_id not in [conversation.participant_1_id, conversation.participant_2_id]:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'conversation': conversation.to_dict(current_user_id)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/conversations/<int:conversation_id>/messages', methods=['GET'])
@token_required
def get_messages(current_user_id, conversation_id):
    """Get all messages in a conversation."""
    try:
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is a participant
        if current_user_id not in [conversation.participant_1_id, conversation.participant_2_id]:
            return jsonify({'error': 'Access denied'}), 403
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        messages_query = conversation.messages.order_by(Message.created_at.desc())
        messages_paginated = messages_query.paginate(page=page, per_page=per_page)
        
        # Mark messages from other user as read
        unread_messages = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user_id,
            Message.is_read == False
        ).all()
        
        for msg in unread_messages:
            msg.is_read = True
        
        db.session.commit()
        
        # Return messages in chronological order (oldest first for display)
        messages_list = [msg.to_dict() for msg in reversed(messages_paginated.items)]
        
        return jsonify({
            'messages': messages_list,
            'total': messages_paginated.total,
            'page': page,
            'pages': messages_paginated.pages,
            'has_more': messages_paginated.has_next
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/conversations/<int:conversation_id>/messages', methods=['POST'])
@token_required
def send_message(current_user_id, conversation_id):
    """Send a message in a conversation."""
    try:
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is a participant
        if current_user_id not in [conversation.participant_1_id, conversation.participant_2_id]:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'Message content is required'}), 400
        
        if len(content) > 5000:
            return jsonify({'error': 'Message too long (max 5000 characters)'}), 400
        
        message = Message(
            conversation_id=conversation_id,
            sender_id=current_user_id,
            content=content
        )
        
        db.session.add(message)
        
        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': message.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/messages/<int:message_id>/read', methods=['PUT'])
@token_required
def mark_message_read(current_user_id, message_id):
    """Mark a message as read."""
    try:
        message = Message.query.get(message_id)
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        conversation = message.conversation
        
        # Verify user is a participant (and not the sender)
        if current_user_id not in [conversation.participant_1_id, conversation.participant_2_id]:
            return jsonify({'error': 'Access denied'}), 403
        
        if message.sender_id == current_user_id:
            return jsonify({'error': 'Cannot mark your own message as read'}), 400
        
        message.is_read = True
        db.session.commit()
        
        return jsonify({
            'message': message.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/conversations/<int:conversation_id>/read-all', methods=['PUT'])
@token_required
def mark_all_read(current_user_id, conversation_id):
    """Mark all messages in a conversation as read."""
    try:
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is a participant
        if current_user_id not in [conversation.participant_1_id, conversation.participant_2_id]:
            return jsonify({'error': 'Access denied'}), 403
        
        # Mark all messages from other user as read
        updated_count = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user_id,
            Message.is_read == False
        ).update({'is_read': True})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'messages_marked_read': updated_count
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/unread-count', methods=['GET'])
@token_required
def get_unread_count(current_user_id):
    """Get total unread message count for current user."""
    try:
        # Get all conversations where user is a participant
        conversations = Conversation.query.filter(
            or_(
                Conversation.participant_1_id == current_user_id,
                Conversation.participant_2_id == current_user_id
            )
        ).all()
        
        total_unread = 0
        for conv in conversations:
            total_unread += conv.get_unread_count(current_user_id)
        
        return jsonify({
            'unread_count': total_unread
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
