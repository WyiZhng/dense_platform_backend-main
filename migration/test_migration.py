"""
Migration Testing Script

This module provides comprehensive testing for all migration services.
"""

import unittest
import os
import tempfile
import shutil
import json
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from database.table import Base, User, UserDetail, DenseReport, Image, UserType, UserSex, ReportStatus
from migration.user_migration import UserMigrationService
from migration.report_migration import ReportMigrationService
from migration.migration_manager import MigrationManager


class TestMigrationServices(unittest.TestCase):
    """Test cases for migration services"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        # Create temporary database
        cls.test_db_path = tempfile.mktemp(suffix='.db')
        cls.test_engine = create_engine(f'sqlite:///{cls.test_db_path}', echo=False)
        
        # Create all tables
        Base.metadata.create_all(cls.test_engine)
        
        # Create temporary storage directory
        cls.test_storage_path = tempfile.mkdtemp()
        cls._create_test_data()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        if os.path.exists(cls.test_storage_path):
            shutil.rmtree(cls.test_storage_path)
    
    @classmethod
    def _create_test_data(cls):
        """Create test data files"""
        # Create directory structure
        users_path = os.path.join(cls.test_storage_path, "users")
        details_path = os.path.join(users_path, "details")
        reports_path = os.path.join(cls.test_storage_path, "reports")
        images_path = os.path.join(cls.test_storage_path, "images")
        avatars_path = os.path.join(cls.test_storage_path, "avatars")
        
        os.makedirs(details_path, exist_ok=True)
        os.makedirs(reports_path, exist_ok=True)
        os.makedirs(images_path, exist_ok=True)
        os.makedirs(avatars_path, exist_ok=True)
        
        # Create test accounts.json
        accounts_data = {
            "testuser1": {
                "password": "hashedpassword1",
                "type": 0
            },
            "testdoctor1": {
                "password": "hashedpassword2",
                "type": 1
            }
        }
        
        with open(os.path.join(users_path, "accounts.json"), 'w') as f:
            json.dump(accounts_data, f)
        
        # Create test user details
        user_detail = {
            "name": "Test User",
            "sex": 1,
            "birth": "1990-01-01",
            "phone": "1234567890",
            "email": "test@example.com",
            "address": "Test Address"
        }
        
        with open(os.path.join(details_path, "testuser1.json"), 'w') as f:
            json.dump(user_detail, f)
        
        # Create test report
        report_data = {
            "id": "test-report-1",
            "user": "testuser1",
            "doctor": "testdoctor1",
            "submitTime": "2024-01-01",
            "current_status": 1,
            "images": ["test-image-1"],
            "diagnose": "Test diagnosis"
        }
        
        with open(os.path.join(reports_path, "test-report-1.json"), 'w') as f:
            json.dump(report_data, f)
        
        # Create test image file
        test_image_data = b"fake image data for testing"
        with open(os.path.join(images_path, "test-image-1.jpg"), 'wb') as f:
            f.write(test_image_data)
        
        # Create test avatar
        with open(os.path.join(avatars_path, "testuser1.png"), 'wb') as f:
            f.write(b"fake avatar data")
    
    def setUp(self):
        """Set up each test"""
        # Clear database
        session = Session(self.test_engine)
        try:
            session.query(User).delete()
            session.query(UserDetail).delete()
            session.query(DenseReport).delete()
            session.query(Image).delete()
            session.commit()
        finally:
            session.close()
    
    def test_user_migration_service(self):
        """Test user migration service"""
        # Patch the engine in the migration service
        migration_service = UserMigrationService(self.test_storage_path)
        
        # Override the engine
        original_engine = migration_service.user_migration.engine if hasattr(migration_service, 'user_migration') else None
        
        # Run migration with test engine
        session = Session(self.test_engine)
        try:
            results = migration_service._migrate_user_accounts(session)
            self.assertTrue(results["users_migrated"] > 0)
            self.assertEqual(len(results["errors"]), 0)
            
            results = migration_service._migrate_user_details(session)
            self.assertTrue(results["details_migrated"] > 0)
            self.assertEqual(len(results["errors"]), 0)
            
            session.commit()
            
            # Verify data
            users = session.query(User).all()
            self.assertEqual(len(users), 2)
            
            user_details = session.query(UserDetail).all()
            self.assertEqual(len(user_details), 1)
            
        finally:
            session.close()
    
    def test_report_migration_service(self):
        """Test report migration service"""
        migration_service = ReportMigrationService(self.test_storage_path)
        
        session = Session(self.test_engine)
        try:
            # First create users (reports depend on users)
            user1 = User(id="testuser1", password="hash1", type=UserType.Patient)
            user2 = User(id="testdoctor1", password="hash2", type=UserType.Doctor)
            session.add(user1)
            session.add(user2)
            session.commit()
            
            # Test image migration
            results = migration_service._migrate_images(session)
            self.assertTrue(results["images_migrated"] > 0)
            self.assertEqual(len(results["errors"]), 0)
            
            # Test report migration
            results = migration_service._migrate_reports(session)
            self.assertTrue(results["reports_migrated"] > 0)
            self.assertEqual(len(results["errors"]), 0)
            
            session.commit()
            
            # Verify data
            images = session.query(Image).all()
            self.assertEqual(len(images), 1)
            
            reports = session.query(DenseReport).all()
            self.assertEqual(len(reports), 1)
            
        finally:
            session.close()
    
    def test_migration_manager(self):
        """Test migration manager"""
        # Create a separate test directory for manager
        manager_storage = tempfile.mkdtemp()
        try:
            # Copy test data
            shutil.copytree(self.test_storage_path, os.path.join(manager_storage, "storage"))
            
            migration_manager = MigrationManager(
                storage_path=os.path.join(manager_storage, "storage"),
                backup_path=os.path.join(manager_storage, "backup")
            )
            
            # Override engines in migration services
            migration_manager.user_migration.engine = self.test_engine
            migration_manager.report_migration.engine = self.test_engine
            
            # Test backup creation
            backup_result = migration_manager._create_backup()
            self.assertTrue(backup_result["success"])
            self.assertTrue(os.path.exists(migration_manager.backup_path))
            
            # Test verification
            session = Session(self.test_engine)
            try:
                verification_result = migration_manager._comprehensive_verification()
                # Should be valid even with empty database
                self.assertIsInstance(verification_result, dict)
                self.assertIn("valid", verification_result)
            finally:
                session.close()
            
        finally:
            shutil.rmtree(manager_storage)
    
    def test_data_validation(self):
        """Test data validation after migration"""
        session = Session(self.test_engine)
        try:
            # Create test data
            user = User(id="testuser", password="hash", type=UserType.Patient)
            session.add(user)
            
            user_detail = UserDetail(
                id="testuser",
                name="Test User",
                sex=UserSex.Male,
                birth=date(1990, 1, 1),
                phone="1234567890",
                email="test@example.com"
            )
            session.add(user_detail)
            
            report = DenseReport(
                id="test-report",
                user="testuser",
                doctor="testuser",
                submitTime=date.today(),
                current_status=ReportStatus.Completed,
                diagnose="Test diagnosis"
            )
            session.add(report)
            
            session.commit()
            
            # Test validation
            migration_service = UserMigrationService()
            validation_result = migration_service.validate_migration(session)
            
            self.assertIsInstance(validation_result, dict)
            self.assertIn("valid", validation_result)
            self.assertTrue(validation_result["users_count"] > 0)
            
        finally:
            session.close()
    
    def test_rollback_functionality(self):
        """Test rollback functionality"""
        session = Session(self.test_engine)
        try:
            # Create test data
            user = User(id="rollback_test", password="hash", type=UserType.Patient)
            session.add(user)
            session.commit()
            
            # Test rollback
            rollback_data = [{"type": "user", "id": "rollback_test"}]
            migration_service = UserMigrationService()
            
            rollback_result = migration_service.rollback_migration(rollback_data)
            self.assertTrue(rollback_result["success"])
            self.assertTrue(rollback_result["rolled_back"] > 0)
            
            # Verify user was removed
            user_check = session.query(User).filter_by(id="rollback_test").first()
            self.assertIsNone(user_check)
            
        finally:
            session.close()


def run_integration_test():
    """Run integration test with actual database"""
    print("Running integration test...")
    
    # Create test storage
    test_storage = tempfile.mkdtemp()
    try:
        # Create minimal test data
        users_path = os.path.join(test_storage, "users")
        os.makedirs(users_path, exist_ok=True)
        
        accounts_data = {
            "integration_test_user": {
                "password": "test_hash",
                "type": 0
            }
        }
        
        with open(os.path.join(users_path, "accounts.json"), 'w') as f:
            json.dump(accounts_data, f)
        
        # Test migration manager
        migration_manager = MigrationManager(storage_path=test_storage)
        status = migration_manager.get_migration_status()
        
        print("Migration Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        print("Integration test completed successfully")
        
    except Exception as e:
        print(f"Integration test failed: {str(e)}")
    finally:
        shutil.rmtree(test_storage)


if __name__ == "__main__":
    # Run unit tests
    print("Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run integration test
    print("\n" + "="*50)
    run_integration_test()