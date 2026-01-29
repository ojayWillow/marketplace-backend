"""WebSocket events for real-time messaging and presence tracking."""

from flask_socketio import emit, join_room, leave_room
from flask import request
import jwt
import os
from app.models import Conversation, Message, User
from app import db
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

# In-memory tracking of online users: {user_id: socket_id}
online_users = {}

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
        """Handle client connection and set user online."""
        try:
            # Get token from auth or query params
            token = None
            if auth and isinstance(auth, dict):
                token = auth.get('token')
            elif request.args.get('token'):
                token = request.args.get('token')
            
            if not token:
                logger.warning(f'Socket connection without token: {request.sid}')
                return False
            
            user_id = get_user_from_token(token)
            if not user_id:
                logger.warning(f'Socket connection with invalid token: {request.sid}')
                return False
            
            # CRITICAL: Set user online in database AND memory
            user = User.query.get(user_id)
            if user:
                user.is_online = True
                user.socket_id = request.sid
                user.last_seen = datetime.utcnow()
                db.session.commit()
                
                # Track in memory for quick lookups
                online_users[user_id] = request.sid
                
                logger.info(f'✅ User {user_id} ({user.username}) CONNECTED: {request.sid}')
                
                # Emit to the connecting user
                emit('connected', {
                    'user_id': user_id,
                    'status': 'online',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Broadcast ONLINE status to all other users
                emit('user_presence', {
                    'user_id': user_id,
                    'is_online': True,
                    'online_status': 'online',
                    'last_seen': None,  # Don't show "last seen" when online
                    'timestamp': datetime.utcnow().isoformat()
                }, broadcast=True, include_self=False)
                
            return True
            
        except Exception as e:
            logger.error(f'Connect error: {e}', exc_info=True)
            return False
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection and set user offline."""
        try:
            # Find which user disconnected
            user_id = None
            for uid, sid in online_users.items():
                if sid == request.sid:
                    user_id = uid
                    break
            
            if not user_id:
                logger.warning(f'Disconnect from unknown socket: {request.sid}')
                return
            
            # CRITICAL: Set user offline in database AND memory
            user = User.query.get(user_id)
            if user:
                user.is_online = False
                user.socket_id = None
                user.last_seen = datetime.utcnow()
                db.session.commit()
                
                # Remove from memory
                if user_id in online_users:
                    del online_users[user_id]
                
                last_seen_display = user.get_last_seen_display()
                
                logger.info(f'❌ User {user_id} ({user.username}) DISCONNECTED: {request.sid}')
                
                # Broadcast OFFLINE status to all users
                emit('user_presence', {
                    'user_id': user_id,
                    'is_online': False,
                    'online_status': 'offline',
                    'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                    'last_seen_display': last_seen_display,
                    'timestamp': datetime.utcnow().isoformat()
                }, broadcast=True)
                
        except Exception as e:
            logger.error(f'Disconnect error: {e}', exc_info=True)
    
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
            
            # Update last_seen on activity (but don't change is_online)
            user = User.query.get(user_id)
            if user:
                user.last_seen = datetime.utcnow()
                db.session.commit()
            
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
            logger.error(f'Join conversation error: {e}', exc_info=True)
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
            logger.error(f'Leave conversation error: {e}', exc_info=True)
    
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
            
            # Update last_seen on activity (but don't change is_online)
            user = User.query.get(user_id)
            if user:
                user.last_seen = datetime.utcnow()
                db.session.commit()
            
            # Broadcast to others in the conversation
            room = f'conversation_{conversation_id}'
            emit('user_typing', {
                'user_id': user_id,
                'is_typing': is_typing,
                'conversation_id': conversation_id
            }, room=room, include_self=False)
            
        except Exception as e:
            logger.error(f'Typing error: {e}', exc_info=True)
    
    @socketio.on('heartbeat')
    def handle_heartbeat(data):
        """Handle heartbeat to keep last_seen fresh (DON'T broadcast presence)."""
        try:
            token = data.get('token')
            if not token:
                return
            
            user_id = get_user_from_token(token)
            if not user_id:
                return
            
            # Only update last_seen timestamp, don't broadcast
            # User is already online via Socket.IO connection
            user = User.query.get(user_id)
            if user:
                user.last_seen = datetime.utcnow()
                # Don't change is_online here - it's managed by connect/disconnect
                db.session.commit()
            
            emit('heartbeat_ack', {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})
            
        except Exception as e:
            logger.error(f'Heartbeat error: {e}', exc_info=True)
    
    @socketio.on('get_presence')
    def handle_get_presence(data):
        """Get online status for specific users."""
        try:
            user_ids = data.get('user_ids', [])
            if not isinstance(user_ids, list):
                user_ids = [user_ids]
            
            presence_data = []
            for target_user_id in user_ids:
                user = User.query.get(target_user_id)
                if user:
                    presence_data.append({
                        'user_id': user.id,
                        'is_online': user.is_online,
                        'online_status': user.get_online_status(),
                        'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                        'last_seen_display': user.get_last_seen_display()
                    })
            
            emit('presence_data', {'users': presence_data})
            
        except Exception as e:
            logger.error(f'Get presence error: {e}', exc_info=True)


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
        logger.error(f'Emit message error: {e}', exc_info=True)


# Utility function to get online users count
def get_online_users_count():
    """Get count of currently online users."""
    return len(online_users)


# Utility function to check if specific user is online
def is_user_connected(user_id):
    """Check if user has active Socket.IO connection."""
    return user_id in online_users
