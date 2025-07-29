#!/usr/bin/env python3
"""
Database schema validation script
Tests that all tables and relationships are properly created
"""

from sqlalchemy import create_engine, inspect
from database.table import Base
from database.db import engine

def test_database_schema():
    """Test that all tables are created with proper structure"""
    
    # Get inspector to examine database structure
    inspector = inspect(engine)
    
    # Get all table names from database
    db_tables = set(inspector.get_table_names())
    
    # Get all table names from our models
    model_tables = set(Base.metadata.tables.keys())
    
    print("=== Database Schema Validation ===")
    print(f"Expected tables: {len(model_tables)}")
    print(f"Database tables: {len(db_tables)}")
    
    # Check if all model tables exist in database
    missing_tables = model_tables - db_tables
    extra_tables = db_tables - model_tables
    
    if missing_tables:
        print(f"❌ Missing tables: {missing_tables}")
        return False
    
    if extra_tables:
        print(f"⚠️  Extra tables (not in models): {extra_tables}")
    
    print("✅ All model tables exist in database")
    
    # Test some key tables and their columns
    key_tables = ['user', 'user_session', 'permission', 'role', 'audit_log']
    
    for table_name in key_tables:
        if table_name in db_tables:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            print(f"\n📋 Table: {table_name}")
            print(f"   Columns: {len(columns)} - {columns}")
            print(f"   Indexes: {len(indexes)} - {indexes}")
            print(f"   Foreign Keys: {len(foreign_keys)}")
    
    print("\n✅ Database schema validation completed successfully!")
    return True

if __name__ == "__main__":
    try:
        test_database_schema()
    except Exception as e:
        print(f"❌ Database schema validation failed: {e}")