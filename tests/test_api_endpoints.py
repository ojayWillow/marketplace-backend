import os
import pytest
from app import create_app
from app import db
from app.models import User, Listing, TaskRequest, TaskResponse, Review

@pytest.fixture(scope="session")
def test_app():
    os.environ["FLASK_ENV"] = "testing"
    os.environ["DATABASE_URI"] = "sqlite:///:memory:"
    app = create_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(test_app):
    return test_app.test_client()

def register_user(client, email="test@example.com", password="password123", username="testuser"):
    response = client.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    if response.status_code not in (200, 201):
        print(f"Registration failed: {response.status_code} - {response.get_json()}")
    assert response.status_code in (200, 201)
    return response.get_json()

def login_user(client, email="test@example.com", password="password123"):
    response = client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert response.status_code == 200
    data = response.get_json()
    return data["token"]

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "ok"

def test_auth_register_and_login_flow(client):
    register_user(client, "user1@example.com", "password123", "user1")
    token = login_user(client, "user1@example.com")
    headers = auth_headers(token)

    profile_resp = client.get("/api/auth/profile", headers=headers)
    assert profile_resp.status_code == 200
    profile_data = profile_resp.get_json()
    assert profile_data.get("email") == "user1@example.com"

def test_create_and_get_listing(client):
    register_user(client, "listing_owner@example.com", "password123", "listingowner")
    token = login_user(client, "listing_owner@example.com")
    headers = auth_headers(token)

    create_resp = client.post("/api/listings", json={
        "title": "Test Listing",
        "description": "Test description",
        "price": 10.0,
        "category": "general"
    }, headers=headers)
    assert create_resp.status_code in (200, 201)
    listing = create_resp.get_json()
    listing_id = listing["id"]

    get_resp = client.get(f"/api/listings/{listing_id}")
    assert get_resp.status_code == 200
    data = get_resp.get_json()
    assert data["title"] == "Test Listing"

def test_create_task_request_and_response_flow(client):
    register_user(client, "creator@example.com", "password123", "creator")
    creator_token = login_user(client, "creator@example.com")
    creator_headers = auth_headers(creator_token)

    register_user(client, "helper@example.com", "password123", "helper")
    helper_token = login_user(client, "helper@example.com")
    helper_headers = auth_headers(helper_token)

    task_resp = client.post("/api/tasks", json={
        "title": "Move furniture",
        "description": "Need help moving",
        "budget": 50.0,
        "location": "Riga",
        "category": "moving"
    }, headers=creator_headers)
    assert task_resp.status_code in (200, 201)
    task = task_resp.get_json()
    task_id = task["id"]

    apply_resp = client.post("/api/task_responses", json={
        "task_id": task_id,
        "message": "I can help",
        "proposed_price": 45.0
    }, headers=helper_headers)
    assert apply_resp.status_code in (200, 201)
    response_data = apply_resp.get_json()
    response_id = response_data["id"]

    update_resp = client.put(f"/api/task_responses/{response_id}", json={
        "status": "accepted"
    }, headers=creator_headers)
    assert update_resp.status_code == 200
    updated = update_resp.get_json()
    assert updated["status"] == "accepted"

def test_create_review_flow(client):
    register_user(client, "reviewer@example.com", "password123", "reviewer")
    reviewer_token = login_user(client, "reviewer@example.com")
    reviewer_headers = auth_headers(reviewer_token)

    register_user(client, "reviewed@example.com", "password123", "reviewed")
    reviewed_token = login_user(client, "reviewed@example.com")

    resp = client.post("/api/reviews", json={
        "reviewed_user_id": 2,
        "rating": 5,
        "comment": "Great job"
    }, headers=reviewer_headers)
    assert resp.status_code in (200, 201)
    review = resp.get_json()
    review_id = review["id"]

    get_resp = client.get(f"/api/reviews/{review_id}")
    assert get_resp.status_code == 200
    data = get_resp.get_json()
    assert data["rating"] == 5
