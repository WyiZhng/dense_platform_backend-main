"""
Migration Manager and Verification Service

This module provides comprehensive migration management, verification, and cleanup
functionality for the entire data migration process.
"""

import json
import os
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database.db import engine
from database.table import Base
from migration.user_migration import UserMigrationService
from migration.report_migration import ReportMigrationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MigrationManager:
    """Comprehensive migration manager for all data migration operations"""
    
    def __init__(self, storage_path: str = "storage", backup_path: str = "storage_backup"):
        self.storage_path = storage_path
        self.backup_path = backup_path
        self.user_migration = UserMigrationService(storage_path)
        self.report_migration = ReportMigrationService(storage_path)
        self.migration_log_file = "migration_log.json"
        
    def run_complete_migration(self) -> Dict[str, any]:
        """
        Run complete migration process with verification and logging
        
        Returns:
            Dict containing comprehensive migration results
        """
        logger.info("Starting complete data migration process...")
        
        migration_results = {
            "success": True,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "user_migration": {},
            "report_migration": {},
            "verification": {},
            "backup_created": False,
            "cleanup_performed": False,
            "errors": [],
            "rollback_data": []
        }
        
        try:
            # Step 1: Create backup of existing file storage
            backup_result = self._create_backup()
            migration_results["backup_created"] = backup_result["success"]
            if not backup_result["success"]:
                migration_results["errors"].extend(backup_result["errors"])
                migration_results["success"] = False
                return migration_results
            
            # Step 2: Run user migration
            logger.info("Running user data migration...")
            user_results = self.user_migration.migrate_all_users()
            migration_results["user_migration"] = user_results
            migration_results["rollback_data"].extend(user_results.get("rollback_data", []))
            
            if not user_results["success"]:
                migration_results["success"] = False
                migration_results["errors"].extend(user_results["errors"])
                return migration_results
            
            # Step 3: Run report migration
            logger.info("Running report data migration...")
            report_results = self.report_migration.migrate_all_reports()
            migration_results["report_migration"] = report_results
            migration_results["rollback_data"].extend(report_results.get("rollback_data", []))
            
            if not report_results["success"]:
                migration_results["success"] = False
                migration_results["errors"].extend(report_results["errors"])
                return migration_results
            
            # Step 4: Comprehensive verification
            logger.info("Running comprehensive verification...")
            verification_results = self._comprehensive_verification()
            migration_results["verification"] = verification_results
            
            if not verification_results["valid"]:
                migration_results["success"] = False
                migration_results["errors"].extend(verification_results["issues"])
                return migration_results
            
            # Step 5: Log migration results
            self._log_migration_results(migration_results)
            
            migration_results["end_time"] = datetime.now().isoformat()
            logger.info("Complete migration process finished successfully")
            
        except Exception as e:
            migration_results["success"] = False
            migration_results["errors"].append(f"Critical migration error: {str(e)}")
            migration_results["end_time"] = datetime.now().isoformat()
            logger.error(f"Critical migration error: {str(e)}")
            
        return migration_results
    
    def _create_backup(self) -> Dict[str, any]:
        """Create backup of existing file storage"""
        logger.info("Creating backup of file storage...")
        
        backup_results = {
            "success": True,
            "backup_path": self.backup_path,
            "errors": []
        }
        
        try:
            if os.path.exists(self.backup_path):
                # Remove existing backup
                shutil.rmtree(self.backup_path)
            
            if os.path.exists(self.storage_path):
                # Create backup
                shutil.copytree(self.storage_path, self.backup_path)
                logger.info(f"Backup created at: {self.backup_path}")
            else:
                backup_results["errors"].append(f"Storage path {self.storage_path} does not exist")
                backup_results["success"] = False
                
        except Exception as e:
            error_msg = f"Error creating backup: {str(e)}"
            backup_results["errors"].append(error_msg)
            backup_results["success"] = False
            logger.error(error_msg)
            
        return backup_results
    
    def _comprehensive_verification(self) -> Dict[str, any]:
        """Run comprehensive verification of migrated data"""
        logger.info("Running comprehensive data verification...")
        
        verification_results = {
            "valid": True,
            "user_verification": {},
            "report_verification": {},
            "cross_reference_verification": {},
            "issues": []
        }
        
        session = Session(engine)
        
        try:
            # Verify user migration
            user_verification = self.user_migration.validate_migration(session)
            verification_results["user_verification"] = user_verification
            
            if not user_verification["valid"]:
                verification_results["valid"] = False
                verification_results["issues"].extend(user_verification["issues"])
            
            # Verify report migration
            report_verification = self.report_migration.validate_migration(session)
            verification_results["report_verification"] = report_verification
            
            if not report_verification["valid"]:
                verification_results["valid"] = False
                verification_results["issues"].extend(report_verification["issues"])
            
            # Cross-reference verification
            cross_ref_verification = self._verify_cross_references(session)
            verification_results["cross_reference_verification"] = cross_ref_verification
            
            if not cross_ref_verification["valid"]:
                verification_results["valid"] = False
                verification_results["issues"].extend(cross_ref_verification["issues"])
            
        except Exception as e:
            verification_results["valid"] = False
            verification_results["issues"].append(f"Verification error: {str(e)}")
            logger.error(f"Verification error: {str(e)}")
            
        finally:
            session.close()
            
        return verification_results
    
    def _verify_cross_references(self, session: Session) -> Dict[str, any]:
        """Verify cross-references between migrated data"""
        logger.info("Verifying cross-references...")
        
        cross_ref_results = {
            "valid": True,
            "issues": []
        }
        
        try:
            from database.table import User, DenseReport, UserDetail
            
            # Check if all report users exist
            reports_with_invalid_users = session.query(DenseReport).outerjoin(
                User, DenseReport.user == User.id
            ).filter(
                User.id.is_(None),
                DenseReport.user.isnot(None)
            ).all()
            
            if reports_with_invalid_users:
                cross_ref_results["valid"] = False
                cross_ref_results["issues"].append(
                    f"Reports with invalid user references: {[r.id for r in reports_with_invalid_users]}"
                )
            
            # Check if all report doctors exist
            reports_with_invalid_doctors = session.query(DenseReport).outerjoin(
                User, DenseReport.doctor == User.id
            ).filter(
                User.id.is_(None),
                DenseReport.doctor.isnot(None)
            ).all()
            
            if reports_with_invalid_doctors:
                cross_ref_results["valid"] = False
                cross_ref_results["issues"].append(
                    f"Reports with invalid doctor references: {[r.id for r in reports_with_invalid_doctors]}"
                )
            
            # Verify data consistency between file counts and database counts
            file_verification = self._verify_file_vs_database_counts(session)
            if not file_verification["valid"]:
                cross_ref_results["valid"] = False
                cross_ref_results["issues"].extend(file_verification["issues"])
            
        except Exception as e:
            cross_ref_results["valid"] = False
            cross_ref_results["issues"].append(f"Cross-reference verification error: {str(e)}")
            
        return cross_ref_results
    
    def _verify_file_vs_database_counts(self, session: Session) -> Dict[str, any]:
        """Verify that database counts match file counts"""
        logger.info("Verifying file vs database counts...")
        
        count_verification = {
            "valid": True,
            "issues": []
        }
        
        try:
            from database.table import User, DenseReport, Image
            
            # Count files
            accounts_file = os.path.join(self.storage_path, "users", "accounts.json")
            file_user_count = 0
            if os.path.exists(accounts_file):
                with open(accounts_file, 'r', encoding='utf-8') as f:
                    accounts_data = json.load(f)
                    file_user_count = len(accounts_data)
            
            reports_path = os.path.join(self.storage_path, "reports")
            file_report_count = 0
            if os.path.exists(reports_path):
                file_report_count = len([f for f in os.listdir(reports_path) if f.endswith('.json')])
            
            images_path = os.path.join(self.storage_path, "images")
            file_image_count = 0
            if os.path.exists(images_path):
                file_image_count = len([f for f in os.listdir(images_path) if os.path.isfile(os.path.join(images_path, f))])
            
            # Count database records
            db_user_count = session.query(User).count()
            db_report_count = session.query(DenseReport).count()
            db_image_count = session.query(Image).count()
            
            # Compare counts
            if file_user_count != db_user_count:
                count_verification["valid"] = False
                count_verification["issues"].append(
                    f"User count mismatch: Files={file_user_count}, Database={db_user_count}"
                )
            
            if file_report_count != db_report_count:
                count_verification["valid"] = False
                count_verification["issues"].append(
                    f"Report count mismatch: Files={file_report_count}, Database={db_report_count}"
                )
            
            if file_image_count != db_image_count:
                count_verification["valid"] = False
                count_verification["issues"].append(
                    f"Image count mismatch: Files={file_image_count}, Database={db_image_count}"
                )
            
        except Exception as e:
            count_verification["valid"] = False
            count_verification["issues"].append(f"Count verification error: {str(e)}")
            
        return count_verification
    
    def cleanup_file_storage(self, confirm: bool = False) -> Dict[str, any]:
        """
        Clean up file storage after successful migration
        
        Args:
            confirm: Must be True to actually perform cleanup
            
        Returns:
            Dict containing cleanup results
        """
        logger.info("Starting file storage cleanup...")
        
        cleanup_results = {
            "success": True,
            "files_removed": 0,
            "directories_removed": 0,
            "errors": []
        }
        
        if not confirm:
            cleanup_results["success"] = False
            cleanup_results["errors"].append("Cleanup not confirmed - set confirm=True to proceed")
            return cleanup_results
        
        try:
            # Remove specific data files while preserving structure
            files_to_remove = [
                os.path.join(self.storage_path, "users", "accounts.json")
            ]
            
            directories_to_clean = [
                os.path.join(self.storage_path, "users", "details"),
                os.path.join(self.storage_path, "reports"),
                os.path.join(self.storage_path, "images"),
                os.path.join(self.storage_path, "avatars"),
                os.path.join(self.storage_path, "comments")
            ]
            
            # Remove specific files
            for file_path in files_to_remove:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleanup_results["files_removed"] += 1
                    logger.info(f"Removed file: {file_path}")
            
            # Clean directories
            for dir_path in directories_to_clean:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    cleanup_results["directories_removed"] += 1
                    logger.info(f"Removed directory: {dir_path}")
            
            logger.info("File storage cleanup completed successfully")
            
        except Exception as e:
            cleanup_results["success"] = False
            cleanup_results["errors"].append(f"Cleanup error: {str(e)}")
            logger.error(f"Cleanup error: {str(e)}")
            
        return cleanup_results
    
    def _log_migration_results(self, results: Dict[str, any]) -> None:
        """Log migration results to file"""
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "migration_results": results
            }
            
            with open(self.migration_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Migration results logged to: {self.migration_log_file}")
            
        except Exception as e:
            logger.error(f"Error logging migration results: {str(e)}")
    
    def rollback_complete_migration(self, rollback_data: List[Dict]) -> Dict[str, any]:
        """
        Rollback complete migration
        
        Args:
            rollback_data: Combined rollback data from all migrations
            
        Returns:
            Dict containing rollback results
        """
        logger.info("Rolling back complete migration...")
        
        rollback_results = {
            "success": True,
            "user_rollback": {},
            "report_rollback": {},
            "backup_restored": False,
            "errors": []
        }
        
        try:
            # Separate rollback data by type
            user_rollback_data = [r for r in rollback_data if r.get("type") in ["user"]]
            report_rollback_data = [r for r in rollback_data if r.get("type") in ["report", "image", "dense_image", "comment"]]
            
            # Rollback report migration first (due to dependencies)
            if report_rollback_data:
                report_rollback = self.report_migration.rollback_migration(report_rollback_data)
                rollback_results["report_rollback"] = report_rollback
                if not report_rollback["success"]:
                    rollback_results["success"] = False
                    rollback_results["errors"].extend(report_rollback["errors"])
            
            # Rollback user migration
            if user_rollback_data:
                user_rollback = self.user_migration.rollback_migration(user_rollback_data)
                rollback_results["user_rollback"] = user_rollback
                if not user_rollback["success"]:
                    rollback_results["success"] = False
                    rollback_results["errors"].extend(user_rollback["errors"])
            
            # Restore backup if available
            if os.path.exists(self.backup_path):
                try:
                    if os.path.exists(self.storage_path):
                        shutil.rmtree(self.storage_path)
                    shutil.copytree(self.backup_path, self.storage_path)
                    rollback_results["backup_restored"] = True
                    logger.info("File storage backup restored")
                except Exception as e:
                    rollback_results["errors"].append(f"Error restoring backup: {str(e)}")
            
        except Exception as e:
            rollback_results["success"] = False
            rollback_results["errors"].append(f"Critical rollback error: {str(e)}")
            
        return rollback_results
    
    def get_migration_status(self) -> Dict[str, any]:
        """Get current migration status from database"""
        logger.info("Checking migration status...")
        
        status = {
            "database_tables_exist": False,
            "data_migrated": False,
            "user_count": 0,
            "report_count": 0,
            "image_count": 0,
            "file_storage_exists": False,
            "backup_exists": False
        }
        
        try:
            # Check if database tables exist
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            required_tables = ['user', 'user_detail', 'dense_report', 'image']
            status["database_tables_exist"] = all(table in tables for table in required_tables)
            
            if status["database_tables_exist"]:
                session = Session(engine)
                try:
                    from database.table import User, DenseReport, Image
                    status["user_count"] = session.query(User).count()
                    status["report_count"] = session.query(DenseReport).count()
                    status["image_count"] = session.query(Image).count()
                    status["data_migrated"] = status["user_count"] > 0 or status["report_count"] > 0
                finally:
                    session.close()
            
            # Check file storage
            status["file_storage_exists"] = os.path.exists(self.storage_path)
            status["backup_exists"] = os.path.exists(self.backup_path)
            
        except Exception as e:
            logger.error(f"Error checking migration status: {str(e)}")
            
        return status


def main():
    """Main function for testing the migration manager"""
    migration_manager = MigrationManager()
    
    # Check current status
    print("Current Migration Status:")
    status = migration_manager.get_migration_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Run complete migration
    print("\nRunning complete migration...")
    results = migration_manager.run_complete_migration()
    
    print("\nMigration Results:")
    print(f"Success: {results['success']}")
    print(f"Start Time: {results['start_time']}")
    print(f"End Time: {results['end_time']}")
    print(f"Backup Created: {results['backup_created']}")
    
    if results['user_migration']:
        print(f"Users Migrated: {results['user_migration'].get('users_migrated', 0)}")
        print(f"User Details Migrated: {results['user_migration'].get('details_migrated', 0)}")
    
    if results['report_migration']:
        print(f"Reports Migrated: {results['report_migration'].get('reports_migrated', 0)}")
        print(f"Images Migrated: {results['report_migration'].get('images_migrated', 0)}")
    
    if results['verification']:
        print(f"Verification Valid: {results['verification'].get('valid', False)}")
    
    if results['errors']:
        print(f"Errors: {results['errors']}")


if __name__ == "__main__":
    main()