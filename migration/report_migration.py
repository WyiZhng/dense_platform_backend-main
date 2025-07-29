"""
Report and Image Data Migration Service

This module handles migration of report data and images from JSON files to database.
Includes dense reports, images, and comments.
"""

import json
import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database.db import engine
from database.table import DenseReport, Image, DenseImage, Comment, ReportStatus, ImageType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportMigrationService:
    """Service for migrating report and image data from file storage to database"""
    
    def __init__(self, storage_path: str = "storage"):
        self.storage_path = storage_path
        self.reports_path = os.path.join(storage_path, "reports")
        self.images_path = os.path.join(storage_path, "images")
        self.comments_path = os.path.join(storage_path, "comments")
        self.migration_log = []
        
    def migrate_all_reports(self) -> Dict[str, any]:
        """
        Migrate all report data from files to database
        
        Returns:
            Dict containing migration results and statistics
        """
        logger.info("Starting report data migration...")
        
        results = {
            "success": True,
            "reports_migrated": 0,
            "images_migrated": 0,
            "dense_images_migrated": 0,
            "comments_migrated": 0,
            "errors": [],
            "rollback_data": []
        }
        
        session = Session(engine)
        
        try:
            # Step 1: Migrate images first (they are referenced by reports)
            images_result = self._migrate_images(session)
            results["images_migrated"] = images_result["images_migrated"]
            results["errors"].extend(images_result["errors"])
            results["rollback_data"].extend(images_result["rollback_data"])
            
            # Step 2: Migrate reports
            reports_result = self._migrate_reports(session)
            results["reports_migrated"] = reports_result["reports_migrated"]
            results["dense_images_migrated"] = reports_result["dense_images_migrated"]
            results["errors"].extend(reports_result["errors"])
            results["rollback_data"].extend(reports_result["rollback_data"])
            
            # Step 3: Migrate comments
            comments_result = self._migrate_comments(session)
            results["comments_migrated"] = comments_result["comments_migrated"]
            results["errors"].extend(comments_result["errors"])
            results["rollback_data"].extend(comments_result["rollback_data"])
            
            # Commit if no errors
            if not results["errors"]:
                session.commit()
                logger.info("Report migration completed successfully")
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
    
    def _migrate_images(self, session: Session) -> Dict[str, any]:
        """Migrate images from files to database"""
        logger.info("Migrating images...")
        
        results = {"images_migrated": 0, "errors": [], "rollback_data": []}
        
        if not os.path.exists(self.images_path):
            results["errors"].append("Images directory not found")
            return results
            
        try:
            for filename in os.listdir(self.images_path):
                try:
                    file_path = os.path.join(self.images_path, filename)
                    
                    # Skip directories
                    if os.path.isdir(file_path):
                        continue
                    
                    # Extract image filename (without extension) for mapping
                    image_filename = os.path.splitext(filename)[0]
                    
                    # Check if image already exists by checking if we have a mapping
                    # We'll create a mapping table to track filename -> database ID
                    if not hasattr(session, '_image_mapping'):
                        session._image_mapping = {}
                    
                    if image_filename in session._image_mapping:
                        logger.warning(f"Image {image_filename} already processed, skipping...")
                        continue
                    
                    # Read image data
                    with open(file_path, 'rb') as f:
                        image_data = f.read()
                    
                    # Get file format
                    file_format = os.path.splitext(filename)[1][1:].lower()  # Remove dot and lowercase
                    if not file_format:
                        file_format = 'jpg'  # Default format
                    
                    # Create image record with auto-increment ID
                    image = Image(
                        data=image_data,
                        upload_time=datetime.now(),
                        format=file_format
                    )
                    
                    session.add(image)
                    session.flush()  # Get the auto-generated ID
                    
                    # Store the mapping from filename to database ID
                    session._image_mapping[image_filename] = image.id
                    
                    results["images_migrated"] += 1
                    results["rollback_data"].append({"type": "image", "id": image.id})
                    
                    logger.info(f"Migrated image: {image_filename} -> ID: {image.id}")
                    
                except Exception as e:
                    error_msg = f"Error migrating image {filename}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error reading images directory: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def _migrate_reports(self, session: Session) -> Dict[str, any]:
        """Migrate reports from JSON files to database"""
        logger.info("Migrating reports...")
        
        results = {"reports_migrated": 0, "dense_images_migrated": 0, "errors": [], "rollback_data": []}
        
        if not os.path.exists(self.reports_path):
            results["errors"].append("Reports directory not found")
            return results
            
        try:
            for filename in os.listdir(self.reports_path):
                if not filename.endswith('.json'):
                    continue
                    
                file_path = os.path.join(self.reports_path, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                    
                    # Use filename as reference, but let database generate ID
                    report_filename = os.path.splitext(filename)[0]
                    
                    # Create a mapping for reports if it doesn't exist
                    if not hasattr(session, '_report_mapping'):
                        session._report_mapping = {}
                    
                    # Check if report already processed
                    if report_filename in session._report_mapping:
                        logger.warning(f"Report {report_filename} already processed, skipping...")
                        continue
                    
                    # Parse submit time
                    submit_time = None
                    if report_data.get("submitTime"):
                        try:
                            submit_time = datetime.strptime(report_data["submitTime"], "%Y-%m-%d").date()
                        except ValueError:
                            logger.warning(f"Invalid submit time for report {report_filename}: {report_data['submitTime']}")
                            submit_time = date.today()
                    
                    # Create dense report (let database generate ID)
                    dense_report = DenseReport(
                        user=report_data.get("user"),
                        doctor=report_data.get("doctor"),
                        submitTime=submit_time,
                        current_status=ReportStatus(report_data.get("current_status", 0)),
                        diagnose=report_data.get("diagnose")
                    )
                    
                    session.add(dense_report)
                    session.flush()  # Get the auto-generated report ID
                    
                    # Store the mapping from filename to database ID
                    session._report_mapping[report_filename] = dense_report.id
                    
                    results["reports_migrated"] += 1
                    results["rollback_data"].append({"type": "report", "id": dense_report.id})
                    
                    # Migrate associated images
                    if "images" in report_data and report_data["images"]:
                        for image_filename in report_data["images"]:
                            try:
                                # Get image mapping if available
                                if not hasattr(session, '_image_mapping'):
                                    session._image_mapping = {}
                                
                                # Find the image database ID using our mapping
                                image_db_id = session._image_mapping.get(image_filename)
                                if not image_db_id:
                                    logger.warning(f"Image {image_filename} not found in mapping for report {report_filename}")
                                    continue
                                
                                # Verify the image exists in database
                                image = session.query(Image).filter_by(id=image_db_id).first()
                                if not image:
                                    logger.warning(f"Image with ID {image_db_id} not found in database for report {report_filename}")
                                    continue
                                
                                # Create dense image relationship
                                dense_image = DenseImage(
                                    report=dense_report.id,
                                    image=image.id,
                                    _type=ImageType.source  # Assume source type for now
                                )
                                
                                session.add(dense_image)
                                results["dense_images_migrated"] += 1
                                results["rollback_data"].append({"type": "dense_image", "report_id": dense_report.id, "image_id": image.id})
                                
                                logger.info(f"Linked image {image_filename} (DB ID: {image.id}) to report {report_filename}")
                                
                            except Exception as e:
                                error_msg = f"Error linking image {image_filename} to report {report_filename}: {str(e)}"
                                results["errors"].append(error_msg)
                                logger.error(error_msg)
                    
                    logger.info(f"Migrated report: {report_filename}")
                    
                except Exception as e:
                    error_msg = f"Error migrating report {filename}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error reading reports directory: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def _migrate_comments(self, session: Session) -> Dict[str, any]:
        """Migrate comments from files to database"""
        logger.info("Migrating comments...")
        
        results = {"comments_migrated": 0, "errors": [], "rollback_data": []}
        
        if not os.path.exists(self.comments_path):
            logger.info("Comments directory not found, skipping comment migration")
            return results
            
        try:
            for filename in os.listdir(self.comments_path):
                if not filename.endswith('.json'):
                    continue
                    
                file_path = os.path.join(self.comments_path, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        comments_data = json.load(f)
                    
                    # Handle both single comment and array of comments
                    if isinstance(comments_data, dict):
                        comments_data = [comments_data]
                    
                    for comment_data in comments_data:
                        try:
                            # Check if comment already exists (if it has an ID)
                            comment_id = comment_data.get("id")
                            if comment_id:
                                existing_comment = session.query(Comment).filter_by(id=comment_id).first()
                                if existing_comment:
                                    logger.warning(f"Comment {comment_id} already exists, skipping...")
                                    continue
                            
                            # Create comment
                            comment = Comment(
                                report=comment_data.get("report"),
                                user=comment_data.get("user"),
                                content=comment_data.get("content"),
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            
                            if comment_id:
                                comment.id = comment_id
                            
                            session.add(comment)
                            session.flush()  # Get the comment ID
                            
                            results["comments_migrated"] += 1
                            results["rollback_data"].append({"type": "comment", "id": comment.id})
                            
                            logger.info(f"Migrated comment: {comment.id}")
                            
                        except Exception as e:
                            error_msg = f"Error migrating individual comment: {str(e)}"
                            results["errors"].append(error_msg)
                            logger.error(error_msg)
                    
                except Exception as e:
                    error_msg = f"Error migrating comments from {filename}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
        except Exception as e:
            error_msg = f"Error reading comments directory: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def validate_migration(self, session: Session) -> Dict[str, any]:
        """
        Validate the migrated report data
        
        Returns:
            Dict containing validation results
        """
        logger.info("Validating report migration...")
        
        validation_results = {
            "valid": True,
            "reports_count": 0,
            "images_count": 0,
            "dense_images_count": 0,
            "comments_count": 0,
            "issues": []
        }
        
        try:
            # Count migrated records
            validation_results["reports_count"] = session.query(DenseReport).count()
            validation_results["images_count"] = session.query(Image).count()
            validation_results["dense_images_count"] = session.query(DenseImage).count()
            validation_results["comments_count"] = session.query(Comment).count()
            
            # Validate data integrity
            # Check for reports without users
            reports_without_users = session.query(DenseReport).filter(
                DenseReport.user.is_(None)
            ).all()
            
            if reports_without_users:
                validation_results["issues"].append(
                    f"{len(reports_without_users)} reports without users: {[r.id for r in reports_without_users]}"
                )
            
            # Check for dense images without valid references
            invalid_dense_images = session.query(DenseImage).outerjoin(
                DenseReport, DenseImage.report == DenseReport.id
            ).outerjoin(
                Image, DenseImage.image == Image.id
            ).filter(
                (DenseReport.id.is_(None)) | (Image.id.is_(None))
            ).all()
            
            if invalid_dense_images:
                validation_results["issues"].append(
                    f"{len(invalid_dense_images)} dense images with invalid references"
                )
            
            # Check for comments without valid report references
            invalid_comments = session.query(Comment).outerjoin(
                DenseReport, Comment.report == DenseReport.id
            ).filter(
                DenseReport.id.is_(None)
            ).all()
            
            if invalid_comments:
                validation_results["issues"].append(
                    f"{len(invalid_comments)} comments with invalid report references"
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
        logger.info("Rolling back report migration...")
        
        rollback_results = {
            "success": True,
            "rolled_back": 0,
            "errors": []
        }
        
        session = Session(engine)
        
        try:
            # Rollback in reverse order to handle dependencies
            for record in reversed(rollback_data):
                try:
                    if record["type"] == "comment":
                        comment = session.query(Comment).filter_by(id=record["id"]).first()
                        if comment:
                            session.delete(comment)
                            rollback_results["rolled_back"] += 1
                            
                    elif record["type"] == "dense_image":
                        dense_image = session.query(DenseImage).filter_by(
                            report=record["report_id"],
                            image=record["image_id"]
                        ).first()
                        if dense_image:
                            session.delete(dense_image)
                            rollback_results["rolled_back"] += 1
                            
                    elif record["type"] == "report":
                        report = session.query(DenseReport).filter_by(id=record["id"]).first()
                        if report:
                            session.delete(report)
                            rollback_results["rolled_back"] += 1
                            
                    elif record["type"] == "image":
                        image = session.query(Image).filter_by(id=record["id"]).first()
                        if image:
                            session.delete(image)
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
    migration_service = ReportMigrationService()
    
    # Run migration
    results = migration_service.migrate_all_reports()
    
    print("Migration Results:")
    print(f"Success: {results['success']}")
    print(f"Reports migrated: {results['reports_migrated']}")
    print(f"Images migrated: {results['images_migrated']}")
    print(f"Dense images migrated: {results['dense_images_migrated']}")
    print(f"Comments migrated: {results['comments_migrated']}")
    
    if results['errors']:
        print(f"Errors: {results['errors']}")
    
    # Validate migration
    if results['success']:
        session = Session(engine)
        validation = migration_service.validate_migration(session)
        session.close()
        
        print("\nValidation Results:")
        print(f"Valid: {validation['valid']}")
        print(f"Reports: {validation['reports_count']}")
        print(f"Images: {validation['images_count']}")
        print(f"Dense Images: {validation['dense_images_count']}")
        print(f"Comments: {validation['comments_count']}")
        
        if validation['issues']:
            print(f"Issues: {validation['issues']}")


if __name__ == "__main__":
    main()