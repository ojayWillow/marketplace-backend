#!/usr/bin/env python3
"""Script to delete a user by phone number."""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.user import User
from app.services.firebase import normalize_phone_number


def delete_user_by_phone(phone_number: str) -> bool:
    """Delete a user by their phone number.
    
    Args:
        phone_number: Phone number to search for (will be normalized)
        
    Returns:
        True if user was deleted, False if not found
    """
    # Normalize the phone number
    normalized_phone = normalize_phone_number(phone_number)
    
    print(f"Looking for user with phone: {normalized_phone}")
    
    # Find user by phone
    user = User.query.filter_by(phone=normalized_phone).first()
    
    if not user:
        print(f"❌ No user found with phone number: {normalized_phone}")
        return False
    
    # Show user details
    print(f"\n📋 Found user:")
    print(f"   ID: {user.id}")
    print(f"   Username: {user.username}")
    print(f"   Email: {user.email}")
    print(f"   Phone: {user.phone}")
    print(f"   Created: {user.created_at}")
    print(f"   Phone Verified: {user.phone_verified}")
    
    # Confirm deletion
    print(f"\n⚠️  WARNING: This will permanently delete the user account!")
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm != 'DELETE':
        print("❌ Deletion cancelled.")
        return False
    
    # Delete user
    try:
        db.session.delete(user)
        db.session.commit()
        print(f"\n✅ User successfully deleted: {user.username} (ID: {user.id})")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error deleting user: {str(e)}")
        return False


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python delete_user_by_phone.py <phone_number>")
        print("Example: python delete_user_by_phone.py +37125953807")
        print("Example: python delete_user_by_phone.py 25953807")
        sys.exit(1)
    
    phone = sys.argv[1]
    
    # Create Flask app context
    app = create_app()
    with app.app_context():
        delete_user_by_phone(phone)
