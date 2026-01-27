#!/usr/bin/env python3
"""Test script for payment endpoints."""

import requests
import json
import sys

# Configuration
BASE_URL = 'http://localhost:5000'
USERNAME = 'testuser'  # Change to your username
PASSWORD = 'password123'  # Change to your password

def login():
    """Login and get auth token."""
    print('\n🔑 Logging in...')
    response = requests.post(
        f'{BASE_URL}/api/auth/login',
        json={'username': USERNAME, 'password': PASSWORD}
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        user_id = data.get('user', {}).get('id')
        print(f'✅ Login successful! User ID: {user_id}')
        return token, user_id
    else:
        print(f'❌ Login failed: {response.text}')
        sys.exit(1)

def get_stripe_config():
    """Get Stripe configuration."""
    print('\n📋 Getting Stripe config...')
    response = requests.get(f'{BASE_URL}/api/payments/config')
    
    if response.status_code == 200:
        config = response.json()
        print(f'✅ Stripe Config:')
        print(f'   Publishable Key: {config.get("publishable_key")[:20]}...')
        print(f'   Platform Fee: {config.get("platform_fee_percent")}%')
        return config
    else:
        print(f'❌ Failed to get config: {response.text}')
        return None

def get_my_tasks(token):
    """Get user's created tasks."""
    print('\n📝 Getting your tasks...')
    response = requests.get(
        f'{BASE_URL}/api/tasks/my-tasks',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    if response.status_code == 200:
        data = response.json()
        tasks = data.get('tasks', [])
        print(f'✅ Found {len(tasks)} tasks')
        
        if tasks:
            for task in tasks[:3]:  # Show first 3
                print(f'   Task ID: {task["id"]} - {task["title"]} (Status: {task["status"]})')
        return tasks
    else:
        print(f'❌ Failed to get tasks: {response.text}')
        return []

def create_payment_intent(token, task_id, amount):
    """Create payment intent for a task."""
    print(f'\n💳 Creating payment intent for Task #{task_id}...')
    print(f'   Amount: €{amount}')
    
    response = requests.post(
        f'{BASE_URL}/api/payments/tasks/{task_id}/pay',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        json={'amount': amount}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f'✅ Payment intent created!')
        print(f'   Transaction ID: {data.get("transaction_id")}')
        print(f'   Amount: €{data.get("amount")}')
        print(f'   Platform Fee: €{data.get("platform_fee")}')
        print(f'   Worker Receives: €{data.get("worker_amount")}')
        print(f'   Client Secret: {data.get("client_secret")[:30]}...')
        return data
    else:
        print(f'❌ Payment failed: {response.text}')
        return None

def get_transactions(token):
    """Get user's transactions."""
    print('\n💰 Getting your transactions...')
    response = requests.get(
        f'{BASE_URL}/api/payments/transactions',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    if response.status_code == 200:
        data = response.json()
        transactions = data.get('transactions', [])
        print(f'✅ Found {len(transactions)} transactions')
        
        for tx in transactions:
            print(f'   Transaction #{tx["id"]}: €{tx["amount"]} - {tx["status"]} (Task #{tx["task_id"]})')
        return transactions
    else:
        print(f'❌ Failed to get transactions: {response.text}')
        return []

def print_curl_command(token, task_id, amount):
    """Print curl command for manual testing."""
    print('\n\n📋 CURL COMMAND (Copy & Paste):')
    print('=' * 80)
    curl_cmd = f'''curl -X POST http://localhost:5000/api/payments/tasks/{task_id}/pay \\\n  -H "Authorization: Bearer {token}" \\\n  -H "Content-Type: application/json" \\\n  -d '{{"{"amount": {amount}}}'}'''
    print(curl_cmd)
    print('=' * 80)

def main():
    print('🚀 Payment System Test Script')
    print('=' * 80)
    
    # Step 1: Login
    token, user_id = login()
    
    # Step 2: Get Stripe config
    stripe_config = get_stripe_config()
    
    # Step 3: Get tasks
    tasks = get_my_tasks(token)
    
    if not tasks:
        print('\n⚠️  No tasks found. Create a task first!')
        return
    
    # Use first task
    task_id = tasks[0]['id']
    amount = 50.00  # Default amount
    
    # Step 4: Create payment intent
    payment_result = create_payment_intent(token, task_id, amount)
    
    # Step 5: Get transactions
    get_transactions(token)
    
    # Step 6: Print curl command
    print_curl_command(token, task_id, amount)
    
    print('\n✅ Test complete!')

if __name__ == '__main__':
    main()
