"""WebSocket events for real-time messaging."""

from flask_socketio import emit, join_room, leave_room
from flask import request
import jwt
import os
from app.models import Conversation, Message, User
from app import db
import logging
from datetime import datetime

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
            
            # Update user last_seen and store socket ID
            user = User.query.get(user_id)
            if user:
                user.update_last_seen()
                db.session.commit()
            
            user_sockets[user_id] = request.sid
            
            logger.info(f'User {user_id} connected: {request.sid}')
            
            # Emit to the connecting user
            emit('connected', {'user_id': user_id})
            
            # Broadcast online status to all connected users
            socketio.emit('user_status_changed', {
                'user_id': user_id,
                'status': 'online',
                'last_seen': datetime.utcnow().isoformat()
            }, broadcast=True, skip_sid=request.sid)
            
            return True
            
        except Exception as e:
            logger.error(f'Connect error: {e}')
            return False
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        try:
            # Find and remove user from socket mapping
            user_id = None
            for uid, sid in list(user_sockets.items()):
                if sid == request.sid:
                    user_id = uid
                    del user_sockets[uid]
                    break
            
            if user_id:
                # Update last_seen on disconnect
                user = User.query.get(user_id)
                if user:
                    user.update_last_seen()
                    db.session.commit()
                
                logger.info(f'User {user_id} disconnected: {request.sid}')
                
                # Broadcast offline status
                socketio.emit('user_status_changed', {
                    'user_id': user_id,
                    'status': 'offline',
                    'last_seen': datetime.utcnow().isoformat()
                }, broadcast=True)
                
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
