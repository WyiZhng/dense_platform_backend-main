"""
Database Migration Tests

This module provides comprehensive tests for database migration functionality including:
- Migration from file storage to database
- Data integrity verification
- Rollback procedures
- Migration status tracking
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime, date
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dense_platform_backend_main.database.table import Base, User, UserDetail, DenseReport, Image, Comment, Doctor, UserType, UserSex, ReportStatus, ImageType
from dense_platform_backend_main.migration.migration_manager import MigrationManager
from dense_platform_backend_main.migration.user_migration import UserMigration
from dense_platform_backend_main.migration.report_migration import ReportMigration

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_user_files(temp_storage_dir):
    """Create sample user files for migration testing"""
    storage_dir = Path(temp_storage_dir)
    
    # Create user directory structure
    user_dir = storage_dir / "user"
    user_dir.mkdir(exist_ok=True)
    
    # Create sample user data files
    user_data = {
        "testuser1": {
            "id": "testuser1",
            "name": "Test User 1",
            "sex": 0,  # Male
            "birth": "1990-01-01",
            "phone": "1234567890",
            "email": "test1@example.com",
            "address": "123 Test St"
        },
        "testuser2": {
            "id": "testuser2",
            "name": "Test User 2",
            "sex": 1,  # Female
            "birth": "1985-05-15",
            "phone": "0987654321",
            "email": "test2@example.com",
            "address": "456 Test Ave"
        }
    }
    
    for user_id, data in user_data.items():
        user_file = user_dir / f"{user_id}.json"
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return storage_dir


@pytest.fixture
def sample_report_files(temp_storage_dir):
    """Create sample report files for migration testing"""
    storage_dir = Path(temp_storage_dir)
    
    # Create report directory structure
    report_dir = storage_dir / "report"
    report_dir.mkdir(exist_ok=True)
    
    # Create sample report data files
    report_data = {
        "report1": {
            "id": "report1",
            "user": "testuser1",
            "doctor": "testdoctor1",
            "submitTime": "2024-01-15",
            "current_status": 0,  # Checking
            "diagnose": "Test diagnosis 1",
            "images": ["1", "2"],
            "Result_img": ["3"]
        },
        "report2": {
            "id": "report2",
            "user": "testuser2",
            "doctor": "testdoctor1",
            "submitTime": "2024-01-20",
            "current_status": 1,  # Completed
            "diagnose": "Test diagnosis 2",
            "images": ["4", "5"],
            "Result_img": ["6", "7"]
        }
    }
    
    for report_id, data in report_data.items():
        report_file = report_dir / f"{report_id}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return storage_dir


@pytest.fixture
def sample_image_files(temp_storage_dir):
    """Create sample image files for migration testing"""
    storage_dir = Path(temp_storage_dir)
    
    # Create image directory structure
    image_dir = storage_dir / "image"
    image_dir.mkdir(exist_ok=True)
    
    # Create sample image files
    for i in range(1, 8):
        image_file = image_dir / f"{i}.jpg"
        # Create fake image data
        fake_image_data = f"fake_image_data_{i}".encode('utf-8')
        with open(image_file, 'wb') as f:
            f.write(fake_image_data)
    
    return storage_dir


class TestUserMigration:
    """Test user data migration functionality"""
    
    def test_migrate_user_data_success(self, db_session, sample_user_files):
        """Test successful user data migration"""
        migration = UserMigration(db_session, str(sample_user_files))
        
        # Run migration
        result = migration.migrate_users()
        assert result is True
        
        # Verify users were migrated
        users = db_session.query(User).all()
        assert len(users) == 2
        
        user_details = db_session.query(UserDetail).all()
        assert len(user_details) == 2
        
        # Verify specific user data
        user1 = db_session.query(UserDetail).filter(UserDetail.id == "testuser1").first()
        assert user1 is not None
        assert user1.name == "Test User 1"
        assert user1.email == "test1@example.com"
        assert user1.sex == UserSex.Male
    
    def test_migrate_user_data_with_existing_users(self, db_session, sample_user_files):
        """Test migration with existing users in database"""
        # Create existing user
        existing_user = User(
            id="testuser1",
            password="existing_password",
            type=UserType.Patient,
            is_active=True
        )
        db_session.add(existing_user)
        db_session.commit()
        
        migration = UserMigration(db_session, str(sample_user_files))
        
        # Run migration
        result = migration.migrate_users()
        assert result is True
        
        # Verify existing user was not overwritten
        user = db_session.query(User).filter(User.id == "testuser1").first()
        assert user.password == "existing_password"
        
        # But user detail should be updated
        user_detail = db_session.query(UserDetail).filter(UserDetail.id == "testuser1").first()
        assert user_detail.name == "Test User 1"
    
    def test_migrate_user_data_invalid_directory(self, db_session):
        """Test migration with invalid directory"""
        migration = UserMigration(db_session, "/nonexistent/directory")
        
        result = migration.migrate_users()
        assert result is False
    
    def test_migrate_user_data_corrupted_file(self, db_session, temp_storage_dir):
        """Test migration with corrupted user file"""
        storage_dir = Path(temp_storage_dir)
        user_dir = storage_dir / "user"
        user_dir.mkdir(exist_ok=True)
        
        # Create corrupted JSON file
        corrupted_file = user_dir / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("invalid json content")
        
        migration = UserMigration(db_session, str(storage_dir))
        
        # Migration should handle corrupted files gracefully
        result = migration.migrate_users()
        # Should return True but skip corrupted files
        assert result is True
    
    def test_verify_user_migration(self, db_session, sample_user_files):
        """Test user migration verification"""
        migration = UserMigration(db_session, str(sample_user_files))
        
        # Run migration first
        migration.migrate_users()
        
        # Verify migration
        verification_result = migration.verify_migration()
        assert verification_result is True
        
        # Check verification details
        stats = migration.get_migration_stats()
        assert stats["total_files"] == 2
        assert stats["migrated_users"] == 2
        assert stats["failed_migrations"] == 0
    
    def test_rollback_user_migration(self, db_session, sample_user_files):
        """Test user migration rollback"""
        migration = UserMigration(db_session, str(sample_user_files))
        
        # Run migration first
        migration.migrate_users()
        
        # Verify data exists
        assert db_session.query(User).count() == 2
        assert db_session.query(UserDetail).count() == 2
        
        # Rollback migration
        rollback_result = migration.rollback_migration()
        assert rollback_result is True
        
        # Verify data was removed
        assert db_session.query(User).count() == 0
        assert db_session.query(UserDetail).count() == 0


class TestReportMigration:
    """Test report data migration functionality"""
    
    def test_migrate_report_data_success(self, db_session, sample_report_files, sample_image_files):
        """Test successful report data migration"""
        # First create some users for the reports
        user1 = User(id="testuser1", password="pass", type=UserType.Patient, is_active=True)
        user2 = User(id="testuser2", password="pass", type=UserType.Patient, is_active=True)
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        migration = ReportMigration(db_session, str(sample_report_files))
        
        # Run migration
        result = migration.migrate_reports()
        assert result is True
        
        # Verify reports were migrated
        reports = db_session.query(DenseReport).all()
        assert len(reports) == 2
        
        # Verify specific report data
        report1 = db_session.query(DenseReport).filter(DenseReport.user == "testuser1").first()
        assert report1 is not None
        assert report1.doctor == "testdoctor1"
        assert report1.diagnose == "Test diagnosis 1"
    
    def test_migrate_image_data_success(self, db_session, sample_image_files):
        """Test successful image data migration"""
        migration = ReportMigration(db_session, str(sample_image_files))
        
        # Run image migration
        result = migration.migrate_images()
        assert result is True
        
        # Verify images were migrated
        images = db_session.query(Image).all()
        assert len(images) == 7  # 7 sample images
        
        # Verify specific image data
        image1 = db_session.query(Image).filter(Image.id == 1).first()
        assert image1 is not None
        assert image1.data == b"fake_image_data_1"
        assert image1.format == "jpg"
    
    def test_migrate_report_with_missing_user(self, db_session, sample_report_files):
        """Test report migration with missing user references"""
        # Don't create users, so reports will have missing user references
        migration = ReportMigration(db_session, str(sample_report_files))
        
        # Migration should handle missing users gracefully
        result = migration.migrate_reports()
        # Should still succeed but may skip reports with missing users
        assert result is True
    
    def test_verify_report_migration(self, db_session, sample_report_files):
        """Test report migration verification"""
        # Create users first
        user1 = User(id="testuser1", password="pass", type=UserType.Patient, is_active=True)
        user2 = User(id="testuser2", password="pass", type=UserType.Patient, is_active=True)
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        migration = ReportMigration(db_session, str(sample_report_files))
        
        # Run migration first
        migration.migrate_reports()
        
        # Verify migration
        verification_result = migration.verify_migration()
        assert verification_result is True
        
        # Check verification details
        stats = migration.get_migration_stats()
        assert stats["total_files"] == 2
        assert stats["migrated_reports"] == 2
    
    def test_rollback_report_migration(self, db_session, sample_report_files):
        """Test report migration rollback"""
        # Create users first
        user1 = User(id="testuser1", password="pass", type=UserType.Patient, is_active=True)
        user2 = User(id="testuser2", password="pass", type=UserType.Patient, is_active=True)
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        migration = ReportMigration(db_session, str(sample_report_files))
        
        # Run migration first
        migration.migrate_reports()
        
        # Verify data exists
        assert db_session.query(DenseReport).count() == 2
        
        # Rollback migration
        rollback_result = migration.rollback_migration()
        assert rollback_result is True
        
        # Verify data was removed
        assert db_session.query(DenseReport).count() == 0


class TestMigrationManager:
    """Test migration manager functionality"""
    
    def test_full_migration_process(self, db_session, sample_user_files, sample_report_files, sample_image_files):
        """Test complete migration process"""
        # Use the same temp directory for all sample files
        storage_path = str(sample_user_files)
        
        manager = MigrationManager(db_session, storage_path)
        
        # Run full migration
        result = manager.run_full_migration()
        assert result is True
        
        # Verify all data was migrated
        assert db_session.query(User).count() == 2
        assert db_session.query(UserDetail).count() == 2
        assert db_session.query(DenseReport).count() == 2
        assert db_session.query(Image).count() == 7
    
    def test_migration_status_tracking(self, db_session, sample_user_files):
        """Test migration status tracking"""
        manager = MigrationManager(db_session, str(sample_user_files))
        
        # Check initial status
        status = manager.get_migration_status()
        assert status["status"] == "not_started"
        
        # Start migration
        manager.run_full_migration()
        
        # Check final status
        status = manager.get_migration_status()
        assert status["status"] == "completed"
        assert status["total_users"] == 2
    
    def test_migration_with_backup(self, db_session, sample_user_files):
        """Test migration with backup creation"""
        manager = MigrationManager(db_session, str(sample_user_files))
        
        # Run migration with backup
        result = manager.run_full_migration(create_backup=True)
        assert result is True
        
        # Verify backup was created
        backup_info = manager.get_backup_info()
        assert backup_info is not None
        assert "backup_path" in backup_info
    
    def test_migration_rollback_full(self, db_session, sample_user_files, sample_report_files):
        """Test full migration rollback"""
        storage_path = str(sample_user_files)
        manager = MigrationManager(db_session, storage_path)
        
        # Run migration first
        manager.run_full_migration()
        
        # Verify data exists
        assert db_session.query(User).count() == 2
        assert db_session.query(UserDetail).count() == 2
        
        # Rollback migration
        rollback_result = manager.rollback_full_migration()
        assert rollback_result is True
        
        # Verify all data was removed
        assert db_session.query(User).count() == 0
        assert db_session.query(UserDetail).count() == 0
        assert db_session.query(DenseReport).count() == 0
    
    def test_migration_error_handling(self, db_session):
        """Test migration error handling"""
        # Use invalid storage path
        manager = MigrationManager(db_session, "/invalid/path")
        
        # Migration should handle errors gracefully
        result = manager.run_full_migration()
        assert result is False
        
        # Check error status
        status = manager.get_migration_status()
        assert status["status"] == "failed"
        assert "error" in status
    
    def test_partial_migration_recovery(self, db_session, sample_user_files):
        """Test recovery from partial migration"""
        manager = MigrationManager(db_session, str(sample_user_files))
        
        # Simulate partial migration by migrating users only
        user_migration = UserMigration(db_session, str(sample_user_files))
        user_migration.migrate_users()
        
        # Check status shows partial completion
        status = manager.get_migration_status()
        assert status["total_users"] == 2
        
        # Complete the migration
        result = manager.run_full_migration()
        assert result is True
        
        # Verify final status
        final_status = manager.get_migration_status()
        assert final_status["status"] == "completed"


class TestDataIntegrityVerification:
    """Test data integrity verification during migration"""
    
    def test_verify_user_data_integrity(self, db_session, sample_user_files):
        """Test user data integrity verification"""
        migration = UserMigration(db_session, str(sample_user_files))
        migration.migrate_users()
        
        # Verify data integrity
        integrity_check = migration.verify_data_integrity()
        assert integrity_check is True
        
        # Check specific integrity aspects
        integrity_details = migration.get_integrity_details()
        assert integrity_details["user_count_match"] is True
        assert integrity_details["user_detail_count_match"] is True
        assert len(integrity_details["missing_users"]) == 0
    
    def test_verify_report_data_integrity(self, db_session, sample_report_files):
        """Test report data integrity verification"""
        # Create users first
        user1 = User(id="testuser1", password="pass", type=UserType.Patient, is_active=True)
        user2 = User(id="testuser2", password="pass", type=UserType.Patient, is_active=True)
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        migration = ReportMigration(db_session, str(sample_report_files))
        migration.migrate_reports()
        
        # Verify data integrity
        integrity_check = migration.verify_data_integrity()
        assert integrity_check is True
        
        # Check specific integrity aspects
        integrity_details = migration.get_integrity_details()
        assert integrity_details["report_count_match"] is True
        assert len(integrity_details["orphaned_reports"]) == 0
    
    def test_detect_data_corruption(self, db_session, sample_user_files):
        """Test detection of data corruption during migration"""
        migration = UserMigration(db_session, str(sample_user_files))
        migration.migrate_users()
        
        # Simulate data corruption by manually modifying database
        user = db_session.query(User).first()
        user.id = None  # This would cause integrity issues
        db_session.commit()
        
        # Verify integrity check detects corruption
        integrity_check = migration.verify_data_integrity()
        assert integrity_check is False
        
        integrity_details = migration.get_integrity_details()
        assert len(integrity_details["corrupted_records"]) > 0


class TestMigrationPerformance:
    """Test migration performance and optimization"""
    
    def test_large_dataset_migration(self, db_session, temp_storage_dir):
        """Test migration with large dataset"""
        storage_dir = Path(temp_storage_dir)
        user_dir = storage_dir / "user"
        user_dir.mkdir(exist_ok=True)
        
        # Create many user files
        for i in range(100):
            user_data = {
                "id": f"user_{i}",
                "name": f"User {i}",
                "sex": i % 2,
                "birth": "1990-01-01",
                "phone": f"123456{i:04d}",
                "email": f"user{i}@example.com",
                "address": f"{i} Test St"
            }
            
            user_file = user_dir / f"user_{i}.json"
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f)
        
        migration = UserMigration(db_session, str(storage_dir))
        
        # Measure migration time
        start_time = datetime.now()
        result = migration.migrate_users()
        end_time = datetime.now()
        
        assert result is True
        migration_time = (end_time - start_time).total_seconds()
        
        # Verify all users were migrated
        assert db_session.query(User).count() == 100
        assert db_session.query(UserDetail).count() == 100
        
        # Performance should be reasonable (less than 10 seconds for 100 users)
        assert migration_time < 10.0
    
    def test_batch_migration_optimization(self, db_session, temp_storage_dir):
        """Test batch migration optimization"""
        storage_dir = Path(temp_storage_dir)
        user_dir = storage_dir / "user"
        user_dir.mkdir(exist_ok=True)
        
        # Create user files
        for i in range(50):
            user_data = {
                "id": f"batch_user_{i}",
                "name": f"Batch User {i}",
                "sex": 0,
                "birth": "1990-01-01",
                "phone": f"555{i:04d}",
                "email": f"batch{i}@example.com",
                "address": f"{i} Batch St"
            }
            
            user_file = user_dir / f"batch_user_{i}.json"
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f)
        
        migration = UserMigration(db_session, str(storage_dir))
        
        # Test batch migration
        result = migration.migrate_users(batch_size=10)
        assert result is True
        
        # Verify all users were migrated
        assert db_session.query(User).count() == 50
        assert db_session.query(UserDetail).count() == 50


if __name__ == "__main__":
    # Run migration tests
    print("Running database migration tests...")
    
    # Test User Migration
    print("Testing User Migration...")
    pytest.main(["-v", "test_database_migration.py::TestUserMigration"])
    
    # Test Report Migration
    print("Testing Report Migration...")
    pytest.main(["-v", "test_database_migration.py::TestReportMigration"])
    
    # Test Migration Manager
    print("Testing Migration Manager...")
    pytest.main(["-v", "test_database_migration.py::TestMigrationManager"])
    
    # Test Data Integrity
    print("Testing Data Integrity Verification...")
    pytest.main(["-v", "test_database_migration.py::TestDataIntegrityVerification"])
    
    print("✅ All database migration tests completed!")