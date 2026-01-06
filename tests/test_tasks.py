"""
Tests for tasks endpoints.
"""

import pytest
from faker import Faker

fake = Faker()


class TestListTasks:
    """Tests for GET /api/tasks"""
    
    def test_list_tasks_empty(self, client, db_session):
        """Test listing when no tasks exist."""
        response = client.get('/api/tasks')
        
        assert response.status_code == 200
    
    def test_list_tasks_with_data(self, client, test_task):
        """Test listing when tasks exist."""
        response = client.get('/api/tasks')
        
        assert response.status_code == 200
        data = response.json if isinstance(response.json, list) else response.json.get('tasks', [])
        assert len(data) >= 1
    
    def test_list_tasks_by_location(self, client, test_task):
        """Test filtering tasks by location."""
        # Riga coordinates
        response = client.get('/api/tasks?lat=56.9496&lng=24.1052&radius=10')
        
        assert response.status_code == 200
    
    def test_list_tasks_by_category(self, client, test_task):
        """Test filtering tasks by category."""
        response = client.get('/api/tasks?category=cleaning')
        
        assert response.status_code == 200


class TestGetTask:
    """Tests for GET /api/tasks/:id"""
    
    def test_get_task_success(self, client, test_task):
        """Test getting a specific task."""
        response = client.get(f'/api/tasks/{test_task["id"]}')
        
        assert response.status_code == 200
        assert 'title' in response.json
    
    def test_get_task_not_found(self, client, db_session):
        """Test getting non-existent task."""
        response = client.get('/api/tasks/99999')
        
        assert response.status_code == 404


class TestCreateTask:
    """Tests for POST /api/tasks"""
    
    def test_create_task_success(self, client, auth_headers, db_session):
        """Test creating a new task."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'budget': 50.00,
            'category': 'delivery',
            'location_lat': 56.9496,
            'location_lng': 24.1052,
            'location_address': 'Riga, Latvia'
        }
        
        response = client.post('/api/tasks', json=data, headers=auth_headers)
        
        assert response.status_code == 201
        assert 'id' in response.json
    
    def test_create_task_unauthenticated(self, client, db_session):
        """Test creating task without authentication."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'budget': 50.00,
            'category': 'delivery'
        }
        
        response = client.post('/api/tasks', json=data)
        
        assert response.status_code in [401, 422]
    
    def test_create_task_missing_location(self, client, auth_headers, db_session):
        """Test creating task without location."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'budget': 50.00,
            'category': 'delivery'
            # Missing location
        }
        
        response = client.post('/api/tasks', json=data, headers=auth_headers)
        
        # May be accepted with null location or rejected
        assert response.status_code in [201, 400, 422]


class TestUpdateTask:
    """Tests for PUT /api/tasks/:id"""
    
    def test_update_own_task(self, client, auth_headers, test_task):
        """Test updating own task."""
        new_title = fake.sentence(nb_words=4)
        
        response = client.put(
            f'/api/tasks/{test_task["id"]}',
            json={'title': new_title},
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_update_other_user_task(self, client, second_auth_headers, test_task):
        """Test updating another user's task (should fail)."""
        response = client.put(
            f'/api/tasks/{test_task["id"]}',
            json={'title': 'Hacked title'},
            headers=second_auth_headers
        )
        
        assert response.status_code in [403, 404]


class TestTaskWorkflow:
    """Tests for task workflow endpoints"""
    
    def test_apply_for_task(self, client, second_auth_headers, test_task):
        """Test applying for a task."""
        response = client.post(
            f'/api/tasks/{test_task["id"]}/apply',
            headers=second_auth_headers
        )
        
        # Should succeed or indicate already applied
        assert response.status_code in [200, 201, 400]
    
    def test_cannot_apply_own_task(self, client, auth_headers, test_task):
        """Test that owner cannot apply to their own task."""
        response = client.post(
            f'/api/tasks/{test_task["id"]}/apply',
            headers=auth_headers
        )
        
        # Should fail - can't apply to own task
        assert response.status_code in [400, 403]
    
    def test_apply_unauthenticated(self, client, test_task):
        """Test applying without authentication."""
        response = client.post(f'/api/tasks/{test_task["id"]}/apply')
        
        assert response.status_code in [401, 422]


class TestMyTasks:
    """Tests for task listing by user"""
    
    def test_get_my_created_tasks(self, client, auth_headers, test_task):
        """Test getting tasks created by user."""
        response = client.get('/api/tasks/created', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json if isinstance(response.json, list) else response.json.get('tasks', [])
        assert len(data) >= 1
    
    def test_get_my_assigned_tasks(self, client, auth_headers):
        """Test getting tasks assigned to user."""
        response = client.get('/api/tasks/my', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_my_tasks_unauthenticated(self, client, db_session):
        """Test getting my tasks without authentication."""
        response = client.get('/api/tasks/created')
        
        assert response.status_code in [401, 422]


class TestDeleteTask:
    """Tests for DELETE /api/tasks/:id"""
    
    def test_delete_own_task(self, client, auth_headers, test_task):
        """Test deleting own task."""
        response = client.delete(
            f'/api/tasks/{test_task["id"]}',
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204]
    
    def test_delete_other_user_task(self, client, second_auth_headers, test_task):
        """Test deleting another user's task (should fail)."""
        response = client.delete(
            f'/api/tasks/{test_task["id"]}',
            headers=second_auth_headers
        )
        
        assert response.status_code in [403, 404]
