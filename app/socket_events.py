"""WebSocket events for real-time messaging."""

from flask_socketio import emit, join_room, leave_room
from flask import request
import jwt
import os
from app.models import Conversation, Message
from app import db
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

# Store user -> socket_id mapping
user_sockets = {}

def get_user_from_token(token):
    """Extract user ID from JWT token."""
    try:
        if token and token.startswith('Bearer '):
            token = token.split(' ')[1]
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return data.get('user_id')
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        return None

def register_socket_events(socketio):
    """Register all Socket.IO event handlers."""
    
    @socketio.on('connect')
    def handle_connect(auth):
        """Handle client connection."""
        try:
            # Get token from auth or query params
            token = None
            if auth and isinstance(auth, dict):
                token = auth.get('token')
            elif request.args.get('token'):
                token = request.args.get('token')
            
            if not token:
                logger.warning('Socket connection without token')
                return False
            
            user_id = get_user_from_token(token)
            if not user_id:
                logger.warning('Socket connection with invalid token')
                return False
            
            # Store socket ID for this user
            user_sockets[user_id] = request.sid
            
            logger.info(f'User {user_id} connected: {request.sid}')
            emit('connected', {'user_id': user_id})
            return True
            
        except Exception as e:
            logger.error(f'Connect error: {e}')
            return False
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        try:
            # Remove user from socket mapping
            user_id = None
            for uid, sid in list(user_sockets.items()):
                if sid == request.sid:
                    user_id = uid
                    del user_sockets[uid]
                    break
            
            if user_id:
                logger.info(f'User {user_id} disconnected: {request.sid}')
        except Exception as e:
            logger.error(f'Disconnect error: {e}')
    
    @socketio.on('join_conversation')
    def handle_join_conversation(data):
        """Join a conversation room."""
        try:
            conversation_id = data.get('conversation_id')
            token = data.get('token')
            
            if not token or not conversation_id:
                emit('error', {'message': 'Missing token or conversation_id'})
                return
            
            user_id = get_user_from_token(token)
            if not user_id:
                emit('error', {'message': 'Invalid token'})
                return
            
            # Verify user is part of conversation
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                emit('error', {'message': 'Conversation not found'})
                return
            
            if user_id not in [conversation.participant_1_id, conversation.participant_2_id]:
                emit('error', {'message': 'Access denied'})
                return
            
            # Join the room
            room = f'conversation_{conversation_id}'
            join_room(room)
            
            logger.info(f'User {user_id} joined conversation {conversation_id}')
            emit('joined_conversation', {'conversation_id': conversation_id})
            
        except Exception as e:
            logger.error(f'Join conversation error: {e}')
            emit('error', {'message': 'Failed to join conversation'})
    
    @socketio.on('leave_conversation')
    def handle_leave_conversation(data):
        """Leave a conversation room."""
        try:
            conversation_id = data.get('conversation_id')
            if not conversation_id:
                return
            
            room = f'conversation_{conversation_id}'
            leave_room(room)
            
            logger.info(f'User left conversation {conversation_id}')
            emit('left_conversation', {'conversation_id': conversation_id})
            
        except Exception as e:
            logger.error(f'Leave conversation error: {e}')
    
    @socketio.on('typing')
    def handle_typing(data):
        """Broadcast typing indicator."""
        try:
            conversation_id = data.get('conversation_id')
            is_typing = data.get('is_typing', False)
            token = data.get('token')
            
            if not token or not conversation_id:
                return
            
            user_id = get_user_from_token(token)
            if not user_id:
                return
            
            # Broadcast to others in the conversation
            room = f'conversation_{conversation_id}'
            emit('user_typing', {
                'user_id': user_id,
                'is_typing': is_typing,
                'conversation_id': conversation_id
            }, room=room, skip_sid=request.sid)
            
        except Exception as e:
            logger.error(f'Typing error: {e}')

# Function to emit new message to conversation room
def emit_new_message(socketio, conversation_id, message_dict):
    """Emit new message to all users in conversation."""
    try:
        room = f'conversation_{conversation_id}'
        socketio.emit('new_message', {
            'message': message_dict,
            'conversation_id': conversation_id
        }, room=room)
        
        logger.info(f'Emitted new message to conversation {conversation_id}')
    except Exception as e:
        logger.error(f'Emit message error: {e}')
