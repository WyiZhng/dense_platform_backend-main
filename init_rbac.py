"""
RBAC Initialization Script

This script initializes the RBAC system with default roles and permissions.
"""

import sys
import os
# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from dense_platform_backend_main.database.db import engine
from dense_platform_backend_main.services.rbac_service import RBACService

# Create database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_rbac_system():
    """Initialize the RBAC system with default roles and permissions"""
    db = SessionLocal()
    
    try:
        print("Initializing RBAC system...")
        
        # Initialize default permissions
        print("Creating default permissions...")
        RBACService.initialize_default_permissions(db)
        
        # Initialize default roles
        print("Creating default roles...")
        RBACService.initialize_default_roles(db)
        
        print("RBAC system initialized successfully!")
        
        # Display created roles and permissions
        print("\nCreated Roles:")
        roles = RBACService.get_all_roles(db)
        for role in roles:
            print(f"  - {role['name']}: {role['description']}")
        
        print("\nCreated Permissions:")
        permissions = RBACService.get_all_permissions(db)
        for perm in permissions:
            print(f"  - {perm['name']}: {perm['resource']}:{perm['action']}")
        
    except Exception as e:
        print(f"Error initializing RBAC system: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_rbac_system()