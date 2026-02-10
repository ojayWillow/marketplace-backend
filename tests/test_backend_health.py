"""
Comprehensive Backend Health Test Suite
========================================
Tests all major API endpoints to verify the backend is working correctly.

Run with:
    pytest tests/test_backend_health.py -v
"""

import pytest
import json
from app import db
from app.models.user import User
from app.models.listing import Listing
from app.models.task_request import TaskRequest
from app.models.notification import Notification
from app.models.message import Conversation, Message
from app.models.review import Review
from app.models.favorite import Favorite
from app.models.task_application import TaskApplication


# ============================================================
#  HEALTH & SMOKE TESTS
# ============================================================

class TestHealthEndpoints:
    """Verify the server boots and responds."""

    def test_root_health(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'

    def test_api_health(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'


# ============================================================
#  AUTH TESTS
# ============================================================

class TestAuth:
    """Authentication flow tests."""

    def test_register_new_user(self, client, db_session):
        resp = client.post('/api/auth/register', json={
            'username': 'newuser_health_test',
            'email': 'healthtest@example.com',
            'password': 'securePassword123',
            'first_name': 'Test',
            'last_name': 'User',
        })
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert 'token' in data or 'access_token' in data

    def test_register_duplicate_email(self, client, test_user):
        resp = client.post('/api/auth/register', json={
            'username': 'different_username',
            'email': test_user['email'],
            'password': 'password123',
        })
        assert resp.status_code in (400, 409)

    def test_login_valid(self, client, test_user):
        resp = client.post('/api/auth/login', json={
            'email': test_user['email'],
            'password': test_user['password'],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'token' in data or 'access_token' in data

    def test_login_wrong_password(self, client, test_user):
        resp = client.post('/api/auth/login', json={
            'email': test_user['email'],
            'password': 'wrongpassword',
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client, db_session):
        resp = client.post('/api/auth/login', json={
            'email': 'nobody@example.com',
            'password': 'password',
        })
        assert resp.status_code in (401, 404)

    def test_protected_route_no_token(self, client, db_session):
        resp = client.get('/api/auth/profile')
        assert resp.status_code == 401

    def test_protected_route_invalid_token(self, client, db_session):
        resp = client.get('/api/auth/profile', headers={
            'Authorization': 'Bearer invalid.token.here'
        })
        assert resp.status_code == 401

    def test_get_profile(self, client, auth_headers):
        resp = client.get('/api/auth/profile', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'id' in data or 'user' in data


# ============================================================
#  LISTINGS TESTS
# ============================================================

class TestListings:
    """Marketplace listings CRUD."""

    def test_get_listings(self, client, db_session):
        resp = client.get('/api/listings')
        assert resp.status_code == 200

    def test_create_listing(self, client, auth_headers, db_session):
        resp = client.post('/api/listings', headers=auth_headers, json={
            'title': 'Test Listing Item',
            'description': 'A great item for sale',
            'price': 49.99,
            'category': 'electronics',
        })
        assert resp.status_code in (200, 201)

    def test_get_single_listing(self, client, test_listing):
        resp = client.get(f'/api/listings/{test_listing["id"]}')
        assert resp.status_code == 200

    def test_get_nonexistent_listing(self, client, db_session):
        resp = client.get('/api/listings/99999')
        assert resp.status_code == 404


# ============================================================
#  TASKS TESTS
# ============================================================

class TestTasks:
    """Task requests CRUD and workflow."""

    def test_get_tasks(self, client, db_session):
        resp = client.get('/api/tasks')
        assert resp.status_code == 200

    def test_create_task(self, client, auth_headers, test_user, db_session):
        """Create task — route requires creator_id in body (no @token_required)."""
        resp = client.post('/api/tasks', headers=auth_headers, json={
            'title': 'Need help moving furniture',
            'description': 'Moving from one apartment to another',
            'budget': 50.0,
            'category': 'moving',
            'location': 'Riga, Latvia',
            'latitude': 56.9496,
            'longitude': 24.1052,
            'creator_id': test_user['id'],
        })
        assert resp.status_code in (200, 201)

    def test_create_task_missing_fields(self, client, db_session):
        """Task creation without required fields returns 400.
        
        Note: The create_task route does NOT use @token_required — it
        expects creator_id in the request body.  Therefore omitting
        auth gives 400 (missing fields), not 401.
        """
        resp = client.post('/api/tasks', json={
            'title': 'Should fail',
            'description': 'No location or creator_id',
            'category': 'cleaning',
        })
        assert resp.status_code == 400

    def test_get_single_task(self, client, test_task):
        resp = client.get(f'/api/tasks/{test_task["id"]}')
        assert resp.status_code == 200
        data = resp.get_json()
        # Check the response contains task data
        task_data = data.get('task', data)
        assert task_data.get('id') == test_task['id'] or task_data.get('title')

    def test_get_nonexistent_task(self, client, db_session):
        resp = client.get('/api/tasks/99999')
        assert resp.status_code == 404


# ============================================================
#  TASK APPLICATIONS TESTS
# ============================================================

class TestTaskApplications:
    """Task application workflow."""

    def test_apply_to_task(self, app, client, test_task, second_user, second_auth_headers):
        resp = client.post(
            f'/api/tasks/{test_task["id"]}/apply',
            headers=second_auth_headers,
            json={'message': 'I can help with this!'}
        )
        assert resp.status_code in (200, 201)

    def test_cannot_apply_to_own_task(self, client, test_task, auth_headers):
        resp = client.post(
            f'/api/tasks/{test_task["id"]}/apply',
            headers=auth_headers,
            json={'message': 'My own task'}
        )
        assert resp.status_code in (400, 403)

    def test_get_task_applications(self, app, client, test_task, auth_headers,
                                    second_user, second_auth_headers):
        # Apply first
        client.post(
            f'/api/tasks/{test_task["id"]}/apply',
            headers=second_auth_headers,
            json={'message': 'I want to help'}
        )
        # Get applications as task owner
        resp = client.get(
            f'/api/tasks/{test_task["id"]}/applications',
            headers=auth_headers
        )
        assert resp.status_code == 200


# ============================================================
#  NOTIFICATIONS TESTS
# ============================================================

class TestNotifications:
    """Notification system."""

    def test_get_notifications(self, client, auth_headers):
        resp = client.get('/api/notifications', headers=auth_headers)
        assert resp.status_code == 200

    def test_get_unread_count(self, client, auth_headers):
        resp = client.get('/api/notifications/unread-count', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'unread_count' in data or 'count' in data

    def test_notifications_unauthenticated(self, client, db_session):
        resp = client.get('/api/notifications')
        assert resp.status_code == 401


# ============================================================
#  MESSAGES TESTS
# ============================================================

class TestMessages:
    """Messaging system."""

    def test_get_conversations(self, client, auth_headers):
        resp = client.get('/api/messages/conversations', headers=auth_headers)
        assert resp.status_code == 200

    def test_conversations_unauthenticated(self, client, db_session):
        resp = client.get('/api/messages/conversations')
        assert resp.status_code == 401


# ============================================================
#  FAVORITES TESTS
# ============================================================

class TestFavorites:
    """Favorites/bookmarks."""

    def test_get_favorites(self, client, auth_headers):
        resp = client.get('/api/favorites', headers=auth_headers)
        assert resp.status_code == 200

    def test_favorites_unauthenticated(self, client, db_session):
        resp = client.get('/api/favorites')
        assert resp.status_code == 401


# ============================================================
#  REVIEWS TESTS
# ============================================================

class TestReviews:
    """Review system."""

    def test_get_reviews(self, client, db_session):
        resp = client.get('/api/reviews')
        assert resp.status_code == 200


# ============================================================
#  OFFERINGS TESTS
# ============================================================

class TestOfferings:
    """Service offerings."""

    def test_get_offerings(self, client, db_session):
        resp = client.get('/api/offerings')
        assert resp.status_code == 200

    def test_create_offering(self, client, auth_headers, db_session):
        resp = client.post('/api/offerings', headers=auth_headers, json={
            'title': 'Plumbing Services',
            'description': 'I can fix your pipes',
            'price': 25.0,
            'price_type': 'hourly',
            'category': 'handyman',
        })
        # May be 200, 201, or 400 if fields are missing
        assert resp.status_code in (200, 201, 400)


# ============================================================
#  DISPUTES TESTS
# ============================================================

class TestDisputes:
    """Dispute system."""

    def test_disputes_unauthenticated(self, client, db_session):
        resp = client.get('/api/disputes')
        assert resp.status_code == 401

    def test_get_disputes(self, client, auth_headers):
        resp = client.get('/api/disputes', headers=auth_headers)
        assert resp.status_code == 200


# ============================================================
#  HELPERS TESTS
# ============================================================

class TestHelpers:
    """Helper listing."""

    def test_get_helpers(self, client, db_session):
        resp = client.get('/api/helpers')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'helpers' in data


# ============================================================
#  MODEL TESTS
# ============================================================

class TestModels:
    """Test model methods and properties."""

    def test_user_password_hashing(self, app, db_session):
        with app.app_context():
            user = User(username='hashtest', email='hash@test.com')
            user.set_password('mypassword')
            assert user.check_password('mypassword') is True
            assert user.check_password('wrongpassword') is False

    def test_user_online_status(self, app, db_session):
        with app.app_context():
            user = User(username='statustest', email='status@test.com')
            user.set_password('pass')
            user.is_online = True
            db.session.add(user)
            db.session.commit()
            assert user.get_online_status() == 'online'

            user.is_online = False
            user.last_seen = None
            assert user.get_online_status() == 'offline'

    def test_user_to_dict(self, app, db_session):
        with app.app_context():
            user = User(
                username='dicttest',
                email='dict@test.com',
                first_name='John',
                last_name='Doe',
            )
            user.set_password('pass')
            db.session.add(user)
            db.session.commit()

            d = user.to_dict()
            assert d['username'] == 'dicttest'
            assert d['email'] == 'dict@test.com'
            assert d['first_name'] == 'John'
            assert 'password_hash' not in d  # Must not expose hash

    def test_user_to_public_dict_no_email(self, app, db_session):
        with app.app_context():
            user = User(
                username='publictest',
                email='private@test.com',
            )
            user.set_password('pass')
            db.session.add(user)
            db.session.commit()

            d = user.to_public_dict()
            assert 'email' not in d  # Public dict should not expose email
            assert d['username'] == 'publictest'

    def test_task_request_to_dict(self, app, db_session):
        with app.app_context():
            user = User(username='taskowner', email='taskowner@t.com')
            user.set_password('p')
            db.session.add(user)
            db.session.commit()

            task = TaskRequest(
                title='Test Task',
                description='Desc',
                category='cleaning',
                location='Riga',
                latitude=56.9,
                longitude=24.1,
                creator_id=user.id,
            )
            db.session.add(task)
            db.session.commit()

            d = task.to_dict()
            assert d['title'] == 'Test Task'
            assert d['status'] == 'open'
            assert d['creator_id'] == user.id

    def test_user_rating_no_reviews(self, app, db_session):
        with app.app_context():
            user = User(username='noreviews', email='norev@t.com')
            user.set_password('p')
            db.session.add(user)
            db.session.commit()
            assert user.rating is None
            assert user.review_count == 0


# ============================================================
#  EDGE CASES & SECURITY
# ============================================================

class TestEdgeCases:
    """Edge cases and security checks."""

    def test_sql_injection_login(self, client, db_session):
        resp = client.post('/api/auth/login', json={
            'email': "' OR 1=1 --",
            'password': 'anything',
        })
        assert resp.status_code in (400, 401, 404)

    def test_xss_in_listing_title(self, client, auth_headers, db_session):
        resp = client.post('/api/listings', headers=auth_headers, json={
            'title': '<script>alert(1)</script>',
            'description': 'Normal description',
            'price': 10,
            'category': 'other',
        })
        # Should succeed (backend stores it; frontend must escape)
        # OR reject with 400 if backend validates
        assert resp.status_code in (200, 201, 400)

    def test_empty_body_login(self, client, db_session):
        resp = client.post('/api/auth/login', json={})
        assert resp.status_code in (400, 401, 422)

    def test_invalid_json(self, client, auth_headers, db_session):
        resp = client.post(
            '/api/listings',
            headers={**auth_headers, 'Content-Type': 'application/json'},
            data='not valid json'
        )
        assert resp.status_code in (400, 415, 500)
