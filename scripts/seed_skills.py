#!/usr/bin/env python3
"""Seed skills database with all predefined skills from categories."""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Skill

# Skills data matching frontend constants
SKILLS_DATA = {
    'cleaning': [
        {'key': 'residential-cleaning', 'name': 'Residential Cleaning'},
        {'key': 'commercial-cleaning', 'name': 'Commercial Cleaning'},
        {'key': 'deep-cleaning', 'name': 'Deep Cleaning'},
        {'key': 'window-cleaning', 'name': 'Window Cleaning'},
        {'key': 'carpet-cleaning', 'name': 'Carpet Cleaning'},
        {'key': 'post-construction-cleaning', 'name': 'Post-Construction Cleaning'},
    ],
    'moving': [
        {'key': 'furniture-moving', 'name': 'Furniture Moving'},
        {'key': 'packing', 'name': 'Packing'},
        {'key': 'loading-unloading', 'name': 'Loading/Unloading'},
        {'key': 'heavy-items', 'name': 'Heavy Items'},
        {'key': 'piano-moving', 'name': 'Piano Moving'},
        {'key': 'office-relocation', 'name': 'Office Relocation'},
    ],
    'heavy-lifting': [
        {'key': 'appliance-moving', 'name': 'Appliance Moving'},
        {'key': 'equipment-moving', 'name': 'Equipment Moving'},
        {'key': 'safe-moving', 'name': 'Safe Moving'},
        {'key': 'machinery-moving', 'name': 'Machinery Moving'},
    ],
    'assembly': [
        {'key': 'furniture-assembly', 'name': 'Furniture Assembly'},
        {'key': 'ikea-assembly', 'name': 'IKEA Assembly'},
        {'key': 'equipment-assembly', 'name': 'Equipment Assembly'},
        {'key': 'gym-equipment', 'name': 'Gym Equipment Assembly'},
        {'key': 'playground-equipment', 'name': 'Playground Equipment'},
    ],
    'mounting': [
        {'key': 'tv-mounting', 'name': 'TV Mounting'},
        {'key': 'shelf-mounting', 'name': 'Shelf Mounting'},
        {'key': 'picture-hanging', 'name': 'Picture Hanging'},
        {'key': 'mirror-mounting', 'name': 'Mirror Mounting'},
        {'key': 'curtain-installation', 'name': 'Curtain Installation'},
    ],
    'handyman': [
        {'key': 'general-repairs', 'name': 'General Repairs'},
        {'key': 'door-repair', 'name': 'Door Repair'},
        {'key': 'drywall-repair', 'name': 'Drywall Repair'},
        {'key': 'tile-repair', 'name': 'Tile Repair'},
        {'key': 'deck-repair', 'name': 'Deck Repair'},
        {'key': 'fence-repair', 'name': 'Fence Repair'},
    ],
    'plumbing': [
        {'key': 'leak-repair', 'name': 'Leak Repair'},
        {'key': 'pipe-installation', 'name': 'Pipe Installation'},
        {'key': 'drain-cleaning', 'name': 'Drain Cleaning'},
        {'key': 'fixture-installation', 'name': 'Fixture Installation'},
        {'key': 'water-heater', 'name': 'Water Heater Service'},
        {'key': 'emergency-plumbing', 'name': 'Emergency Plumbing'},
    ],
    'electrical': [
        {'key': 'wiring', 'name': 'Wiring'},
        {'key': 'lighting-installation', 'name': 'Lighting Installation'},
        {'key': 'circuit-repair', 'name': 'Circuit Repair'},
        {'key': 'outlet-installation', 'name': 'Outlet Installation'},
        {'key': 'safety-inspection', 'name': 'Safety Inspection'},
        {'key': 'panel-upgrade', 'name': 'Panel Upgrade'},
    ],
    'painting': [
        {'key': 'interior-painting', 'name': 'Interior Painting'},
        {'key': 'exterior-painting', 'name': 'Exterior Painting'},
        {'key': 'wallpaper-installation', 'name': 'Wallpaper Installation'},
        {'key': 'cabinet-painting', 'name': 'Cabinet Painting'},
        {'key': 'deck-staining', 'name': 'Deck Staining'},
        {'key': 'pressure-washing', 'name': 'Pressure Washing'},
    ],
    'gardening': [
        {'key': 'lawn-mowing', 'name': 'Lawn Mowing'},
        {'key': 'hedge-trimming', 'name': 'Hedge Trimming'},
        {'key': 'tree-pruning', 'name': 'Tree Pruning'},
        {'key': 'landscaping', 'name': 'Landscaping'},
        {'key': 'garden-design', 'name': 'Garden Design'},
        {'key': 'weed-removal', 'name': 'Weed Removal'},
    ],
    'car-wash': [
        {'key': 'exterior-wash', 'name': 'Exterior Wash'},
        {'key': 'interior-detailing', 'name': 'Interior Detailing'},
        {'key': 'full-detailing', 'name': 'Full Detailing'},
        {'key': 'waxing-polishing', 'name': 'Waxing & Polishing'},
        {'key': 'headlight-restoration', 'name': 'Headlight Restoration'},
    ],
    'delivery': [
        {'key': 'food-delivery', 'name': 'Food Delivery'},
        {'key': 'package-delivery', 'name': 'Package Delivery'},
        {'key': 'grocery-delivery', 'name': 'Grocery Delivery'},
        {'key': 'courier-service', 'name': 'Courier Service'},
        {'key': 'same-day-delivery', 'name': 'Same-Day Delivery'},
    ],
    'shopping': [
        {'key': 'grocery-shopping', 'name': 'Grocery Shopping'},
        {'key': 'personal-shopping', 'name': 'Personal Shopping'},
        {'key': 'gift-shopping', 'name': 'Gift Shopping'},
        {'key': 'errands', 'name': 'Errands'},
    ],
    'pet-care': [
        {'key': 'dog-walking', 'name': 'Dog Walking'},
        {'key': 'pet-sitting', 'name': 'Pet Sitting'},
        {'key': 'pet-grooming', 'name': 'Pet Grooming'},
        {'key': 'pet-training', 'name': 'Pet Training'},
        {'key': 'pet-transportation', 'name': 'Pet Transportation'},
    ],
    'tutoring': [
        {'key': 'math-tutoring', 'name': 'Math Tutoring'},
        {'key': 'language-tutoring', 'name': 'Language Tutoring'},
        {'key': 'science-tutoring', 'name': 'Science Tutoring'},
        {'key': 'music-lessons', 'name': 'Music Lessons'},
        {'key': 'test-prep', 'name': 'Test Preparation'},
        {'key': 'homework-help', 'name': 'Homework Help'},
    ],
    'tech-help': [
        {'key': 'computer-repair', 'name': 'Computer Repair'},
        {'key': 'phone-repair', 'name': 'Phone Repair'},
        {'key': 'software-installation', 'name': 'Software Installation'},
        {'key': 'network-setup', 'name': 'Network Setup'},
        {'key': 'smart-home-setup', 'name': 'Smart Home Setup'},
        {'key': 'data-recovery', 'name': 'Data Recovery'},
    ],
    'beauty': [
        {'key': 'haircut', 'name': 'Haircut'},
        {'key': 'hair-styling', 'name': 'Hair Styling'},
        {'key': 'manicure-pedicure', 'name': 'Manicure/Pedicure'},
        {'key': 'makeup', 'name': 'Makeup'},
        {'key': 'massage', 'name': 'Massage'},
        {'key': 'skincare', 'name': 'Skincare'},
    ],
    'hospitality': [
        {'key': 'customer-service', 'name': 'Customer Service'},
        {'key': 'bartending', 'name': 'Bartending'},
        {'key': 'waiting-tables', 'name': 'Waiting Tables'},
        {'key': 'hotel-management', 'name': 'Hotel Management'},
        {'key': 'event-catering', 'name': 'Event Catering'},
        {'key': 'barista', 'name': 'Barista'},
        {'key': 'cooking', 'name': 'Cooking'},
        {'key': 'event-planning', 'name': 'Event Planning'},
    ],
    'construction': [
        {'key': 'carpentry', 'name': 'Carpentry'},
        {'key': 'masonry', 'name': 'Masonry'},
        {'key': 'roofing', 'name': 'Roofing'},
        {'key': 'drywall', 'name': 'Drywall'},
        {'key': 'concrete-work', 'name': 'Concrete Work'},
        {'key': 'welding', 'name': 'Welding'},
        {'key': 'demolition', 'name': 'Demolition'},
        {'key': 'framing', 'name': 'Framing'},
        {'key': 'flooring', 'name': 'Flooring'},
        {'key': 'tile-work', 'name': 'Tile Work'},
    ],
    'other': [
        {'key': 'general-help', 'name': 'General Help'},
        {'key': 'odd-jobs', 'name': 'Odd Jobs'},
    ],
}


def seed_skills():
    """Seed the skills database."""
    app = create_app()
    
    with app.app_context():
        print("Starting skills seeding...")
        
        # Count existing skills
        existing_count = Skill.query.count()
        print(f"Found {existing_count} existing skills")
        
        added_count = 0
        updated_count = 0
        
        # Iterate through all categories and skills
        for category, skills in SKILLS_DATA.items():
            print(f"\nProcessing category: {category}")
            
            for skill_data in skills:
                # Check if skill already exists
                existing_skill = Skill.query.filter_by(key=skill_data['key']).first()
                
                if existing_skill:
                    # Update existing skill
                    existing_skill.name = skill_data['name']
                    existing_skill.category = category
                    existing_skill.is_active = True
                    updated_count += 1
                    print(f"  Updated: {skill_data['name']}")
                else:
                    # Create new skill
                    new_skill = Skill(
                        key=skill_data['key'],
                        name=skill_data['name'],
                        category=category,
                        is_active=True
                    )
                    db.session.add(new_skill)
                    added_count += 1
                    print(f"  Added: {skill_data['name']}")
        
        # Commit all changes
        db.session.commit()
        
        # Summary
        total_count = Skill.query.count()
        print(f"\n" + "="*50)
        print(f"Skills seeding completed!")
        print(f"Added: {added_count} new skills")
        print(f"Updated: {updated_count} existing skills")
        print(f"Total skills in database: {total_count}")
        print("="*50)


if __name__ == '__main__':
    seed_skills()
