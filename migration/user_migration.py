"""
User Data Migration Service

This module handles migration of user data from JSON files to database.
Includes user accounts, user details, and doctor information.
"""

import json
import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database.db import engine
from database.table import User, UserDetail, Doctor, UserType, UserSex, Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserMigrationService:
    """Service for migrating user data from file storage to database"""
    
    def __init__(self, storage_path: str = "storage"):
        self.storage_path = storage_path
        self.users_path = os.path.join(storage_path, "users")
        self.avatars_path = os.path.join(storage_path, "avatars")
        self.migration_log = []
        
    def migrate_all_users(self) -> Dict[str, any]:
        """
        Migrate all user data from files to database
        
        Returns:
            Dict containing migration results and statistics
        """
        logger.info("Starting user data migration...")
        
        results = {
            "success": True,
            "users_migrated": 0,
            "details_migrated": 0,
            "doctors_migrated": 0,
            "avatars_migrated": 0,
            "errors": [],
            "rollback_data": []
        }
        
        session = Session(engine)
        
        try:
            # Step 1: Migrate user accounts
            accounts_result = self._migrate_user_accounts(session)
            results.update(accounts_result)
            
            # Step 2: Migrate user details
            details_result = self._migrate_user_details(session)
            results["details_migrated"] = details_result["details_migrated"]
            results["errors"].extend(details_result["errors"])
            
            # Step 3: Migrate avatars
            avatars_result = self._migrate_avatars(session)
            results["avatars_migrated"] = avatars_result["avatars_migrated"]
            results["errors"].extend(avatars_result["errors"])
            
            # Step 4: Migrate doctor information
            doctors_result = self._migrate_doctors(session)
            results["doctors_migrated"] = doctors_result["doctors_migrated"]
            results["errors"].extend(doctors_result["errors"])
            
            # Commit if no errors
            if not results["errors"]:
                session.commit()
                logger.info("User migration completed successfully")
            else:
                session.rollback()
                results["success"] = False
                logger.error(f"Migration failed with {len(results['errors'])} errors")
                
        except Exception as e:
            session.rollback()
            results["success"] = False
            results["errors"].append(f"Critical migration error: {str(e)}")
            logger.error(f"Critical migration error: {str(e)}")
            
        finally:
            session.close()
            
        return results
    
    def _migrate_user_accounts(self, session: Session) -> Dict[str, any]:
        """Migrate user accounts from accounts.json"""
        logger.info("Migrating user accounts...")
        
        accounts_file = os.path.join(self.users_path, "accounts.json")
        results = {"users_migrated": 0, "errors": [], "rollback_data": []}
        
        if not os.path.exists(accounts_file):
            results["errors"].append("accounts.json file not found")
            return results
            
        try:
            with open(accounts_file, 'r', encoding='utf-8') as f:
                accounts_data = json.load(f)
                
            for username, account_info in accounts_data.items():
                try:
                    # Check if user already exists
                    existing_user = session.query(User).filter_by(id=username).first()
                    if existing_user:
                        logger.warning(f"User {username} already exists, skipping...")
                        continue
                    
                    # Create new user
                    user = User(
                        id=username,
                        password=account_info["password"],
                        type=UserType(account_info["type"]),
                        is_active=True,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    
                    session.add(user)
                    results["users_migrated"] += 1
                    results["rollback_data"].append({"type": "user", "id": username})
                    
                    logger.info(f"Migrated user: {username}")
                    
                except Exception as e:
                    error_msg = f"Error migrating user {username}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error reading accounts.json: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def _migrate_user_details(self, session: Session) -> Dict[str, any]:
        """Migrate user details from individual JSON files"""
        logger.info("Migrating user details...")
        
        details_path = os.path.join(self.users_path, "details")
        results = {"details_migrated": 0, "errors": []}
        
        if not os.path.exists(details_path):
            results["errors"].append("User details directory not found")
            return results
            
        try:
            for filename in os.listdir(details_path):
                if not filename.endswith('.json'):
                    continue
                    
                username = filename.replace('.json', '')
                file_path = os.path.join(details_path, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        detail_data = json.load(f)
                    
                    # Check if user exists
                    user = session.query(User).filter_by(id=username).first()
                    if not user:
                        results["errors"].append(f"User {username} not found for details migration")
                        continue
                    
                    # Check if user detail already exists
                    existing_detail = session.query(UserDetail).filter_by(id=username).first()
                    if existing_detail:
                        logger.warning(f"User detail for {username} already exists, skipping...")
                        continue
                    
                    # Parse birth date
                    birth_date = None
                    if detail_data.get("birth"):
                        try:
                            birth_date = datetime.strptime(detail_data["birth"], "%Y-%m-%d").date()
                        except ValueError:
                            logger.warning(f"Invalid birth date for user {username}: {detail_data['birth']}")
                    
                    # Create user detail
                    user_detail = UserDetail(
                        id=username,
                        name=detail_data.get("name"),
                        sex=UserSex(detail_data["sex"]) if detail_data.get("sex") is not None else None,
                        birth=birth_date,
                        phone=detail_data.get("phone"),
                        email=detail_data.get("email"),
                        address=detail_data.get("address")
                    )
                    
                    session.add(user_detail)
                    results["details_migrated"] += 1
                    
                    logger.info(f"Migrated user detail: {username}")
                    
                except Exception as e:
                    error_msg = f"Error migrating user detail {username}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error reading user details directory: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def _migrate_avatars(self, session: Session) -> Dict[str, any]:
        """Migrate user avatars to database"""
        logger.info("Migrating user avatars...")
        
        results = {"avatars_migrated": 0, "errors": []}
        
        if not os.path.exists(self.avatars_path):
            results["errors"].append("Avatars directory not found")
            return results
            
        try:
            for filename in os.listdir(self.avatars_path):
                try:
                    # Extract username from filename (remove extension)
                    username = os.path.splitext(filename)[0]
                    # Handle special cases like "口腔科郑武_Test.jpeg"
                    if '_' in username:
                        username = username.split('_')[-1]
                    
                    file_path = os.path.join(self.avatars_path, filename)
                    
                    # Read image data
                    with open(file_path, 'rb') as f:
                        image_data = f.read()
                    
                    # Get file format
                    file_format = os.path.splitext(filename)[1][1:].lower()  # Remove dot and lowercase
                    
                    # Create image record
                    image = Image(
                        data=image_data,
                        upload_time=datetime.now(),
                        format=file_format
                    )
                    
                    session.add(image)
                    session.flush()  # Get the image ID
                    
                    # Update user detail with avatar
                    user_detail = session.query(UserDetail).filter_by(id=username).first()
                    if user_detail:
                        user_detail.avatar = image.id
                        results["avatars_migrated"] += 1
                        logger.info(f"Migrated avatar for user: {username}")
                    else:
                        logger.warning(f"User detail not found for avatar: {username}")
                        
                except Exception as e:
                    error_msg = f"Error migrating avatar {filename}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error reading avatars directory: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def _migrate_doctors(self, session: Session) -> Dict[str, any]:
        """Migrate doctor information"""
        logger.info("Migrating doctor information...")
        
        results = {"doctors_migrated": 0, "errors": []}
        
        try:
            # Get all users with doctor type
            doctors = session.query(User).filter_by(type=UserType.Doctor).all()
            
            for doctor_user in doctors:
                try:
                    # Check if doctor record already exists
                    existing_doctor = session.query(Doctor).filter_by(id=doctor_user.id).first()
                    if existing_doctor:
                        logger.warning(f"Doctor record for {doctor_user.id} already exists, skipping...")
                        continue
                    
                    # Create doctor record with default values
                    # Note: Since there's no doctor-specific data in files, we create with defaults
                    doctor = Doctor(
                        id=doctor_user.id,
                        position="Doctor",  # Default position
                        workplace="Hospital"  # Default workplace
                    )
                    
                    session.add(doctor)
                    results["doctors_migrated"] += 1
                    
                    logger.info(f"Created doctor record: {doctor_user.id}")
                    
                except Exception as e:
                    error_msg = f"Error creating doctor record for {doctor_user.id}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error migrating doctors: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def validate_migration(self, session: Session) -> Dict[str, any]:
        """
        Validate the migrated user data
        
        Returns:
            Dict containing validation results
        """
        logger.info("Validating user migration...")
        
        validation_results = {
            "valid": True,
            "users_count": 0,
            "details_count": 0,
            "doctors_count": 0,
            "avatars_count": 0,
            "issues": []
        }
        
        try:
            # Count migrated records
            validation_results["users_count"] = session.query(User).count()
            validation_results["details_count"] = session.query(UserDetail).count()
            validation_results["doctors_count"] = session.query(Doctor).count()
            validation_results["avatars_count"] = session.query(UserDetail).filter(
                UserDetail.avatar.isnot(None)
            ).count()
            
            # Validate data integrity
            users_without_details = session.query(User).outerjoin(UserDetail).filter(
                UserDetail.id.is_(None)
            ).all()
            
            if users_without_details:
                validation_results["issues"].append(
                    f"{len(users_without_details)} users without details: {[u.id for u in users_without_details]}"
                )
            
            # Validate doctor records
            doctor_users = session.query(User).filter_by(type=UserType.Doctor).all()
            doctors_without_records = []
            
            for doctor_user in doctor_users:
                doctor_record = session.query(Doctor).filter_by(id=doctor_user.id).first()
                if not doctor_record:
                    doctors_without_records.append(doctor_user.id)
            
            if doctors_without_records:
                validation_results["issues"].append(
                    f"Doctor users without doctor records: {doctors_without_records}"
                )
            
            if validation_results["issues"]:
                validation_results["valid"] = False
                
        except Exception as e:
            validation_results["valid"] = False
            validation_results["issues"].append(f"Validation error: {str(e)}")
            
        return validation_results
    
    def rollback_migration(self, rollback_data: List[Dict]) -> Dict[str, any]:
        """
        Rollback migration changes
        
        Args:
            rollback_data: List of records to rollback
            
        Returns:
            Dict containing rollback results
        """
        logger.info("Rolling back user migration...")
        
        rollback_results = {
            "success": True,
            "rolled_back": 0,
            "errors": []
        }
        
        session = Session(engine)
        
        try:
            for record in rollback_data:
                try:
                    if record["type"] == "user":
                        user = session.query(User).filter_by(id=record["id"]).first()
                        if user:
                            session.delete(user)
                            rollback_results["rolled_back"] += 1
                            
                except Exception as e:
                    error_msg = f"Error rolling back {record}: {str(e)}"
                    rollback_results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            if not rollback_results["errors"]:
                session.commit()
                logger.info("Rollback completed successfully")
            else:
                session.rollback()
                rollback_results["success"] = False
                
        except Exception as e:
            session.rollback()
            rollback_results["success"] = False
            rollback_results["errors"].append(f"Critical rollback error: {str(e)}")
            
        finally:
            session.close()
            
        return rollback_results


def main():
    """Main function for testing the migration service"""
    migration_service = UserMigrationService()
    
    # Run migration
    results = migration_service.migrate_all_users()
    
    print("Migration Results:")
    print(f"Success: {results['success']}")
    print(f"Users migrated: {results['users_migrated']}")
    print(f"Details migrated: {results['details_migrated']}")
    print(f"Doctors migrated: {results['doctors_migrated']}")
    print(f"Avatars migrated: {results['avatars_migrated']}")
    
    if results['errors']:
        print(f"Errors: {results['errors']}")
    
    # Validate migration
    if results['success']:
        session = Session(engine)
        validation = migration_service.validate_migration(session)
        session.close()
        
        print("\nValidation Results:")
        print(f"Valid: {validation['valid']}")
        print(f"Users: {validation['users_count']}")
        print(f"Details: {validation['details_count']}")
        print(f"Doctors: {validation['doctors_count']}")
        print(f"Avatars: {validation['avatars_count']}")
        
        if validation['issues']:
            print(f"Issues: {validation['issues']}")


if __name__ == "__main__":
    main()