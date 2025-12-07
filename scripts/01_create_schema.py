#!/usr/bin/env python3
"""
Script to create PostgreSQL database schema
Run this first before loading data
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import db


def main():
    """Create database schema"""
    print("=" * 60)
    print("Creating PostgreSQL Schema for Route Restrictions Database")
    print("=" * 60)
    
    # Path to schema file
    schema_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'src', 'db', 'schema.sql'
    )
    
    if not os.path.exists(schema_file):
        print(f"❌ Schema file not found: {schema_file}")
        return 1
    
    try:
        # Execute schema
        print(f"\n📄 Executing schema from: {schema_file}")
        db.execute_script(schema_file)
        
        # Verify tables created
        print("\n✅ Schema created successfully!")
        print("\nVerifying tables...")
        
        tables = db.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        print(f"\n📊 Created {len(tables)} tables:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        # Verify views
        views = db.execute_query("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        if views:
            print(f"\n👁️  Created {len(views)} views:")
            for view in views:
                print(f"   - {view['table_name']}")
        
        print("\n" + "=" * 60)
        print("✅ Database setup complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run: python scripts/02_load_data.py")
        print("  2. Run: python scripts/03_verify_data.py")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error creating schema: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
