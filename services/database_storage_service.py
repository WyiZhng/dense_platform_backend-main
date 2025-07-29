"""
Database Storage Service

This module provides database-based storage operations to replace file-based storage.
It handles user details, reports, images, comments, and other data using database operations.
"""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime, date
import json
import uuid
import hashlib
from pathlib import Path

from dense_platform_backend_main.database.table import (
    User, UserDetail, Doctor, DenseReport, DenseImage, Comment, Image,
    Avatar, ResultImage, UserType, UserSex, ReportStatus, ImageType, AuditLog
)


class DatabaseStorageService:
    """Database-based storage service to replace file operations"""
    
    @staticmethod
    def save_user_detail(db: Session, user_id: str, detail_data: Dict[str, Any]) -> bool:
        """
        Save user detail information to database
        
        Args:
            db: Database session
            user_id: User ID
            detail_data: User detail data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if user detail already exists
            user_detail = db.query(UserDetail).filter(UserDetail.id == user_id).first()
            
            if user_detail:
                # Update existing record
                for key, value in detail_data.items():
                    if hasattr(user_detail, key) and value is not None:
                        setattr(user_detail, key, value)
            else:
                # Create new record
                user_detail = UserDetail(id=user_id, **detail_data)
                db.add(user_detail)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error saving user detail: {e}")
            return False
    
    @staticmethod
    def load_user_detail(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Load user detail information from database
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User detail dictionary or None if not found
        """
        try:
            user_detail = db.query(UserDetail).filter(UserDetail.id == user_id).first()
            
            if not user_detail:
                return None
            
            return {
                "id": user_detail.id,
                "name": user_detail.name,
                "sex": user_detail.sex,
                "birth": user_detail.birth.isoformat() if user_detail.birth else None,
                "phone": user_detail.phone,
                "email": user_detail.email,
                "address": user_detail.address,
                "avatar": user_detail.avatar
            }
            
        except Exception as e:
            print(f"Error loading user detail: {e}")
            return None
    
    @staticmethod
    def save_image(db: Session, image_data: bytes, filename: str, format: str = "jpg") -> Optional[str]:
        """
        Save image data to database
        
        Args:
            db: Database session
            image_data: Image binary data
            filename: Original filename
            format: Image format
            
        Returns:
            Image ID if successful, None otherwise
        """
        try:
            image = Image(
                data=image_data,
                format=format,
                upload_time=datetime.now()
            )
            db.add(image)
            db.flush()  # Get the ID
            
            db.commit()
            return str(image.id)
            
        except Exception as e:
            db.rollback()
            print(f"Error saving image: {e}")
            return None
    
    @staticmethod
    def load_image(db: Session, image_id: str) -> Optional[bytes]:
        """
        Load image data from database
        
        Args:
            db: Database session
            image_id: Image ID
            
        Returns:
            Image binary data or None if not found
        """
        try:
            image = db.query(Image).filter(Image.id == int(image_id)).first()
            
            if not image:
                return None
            
            return image.data
            
        except Exception as e:
            print(f"Error loading image: {e}")
            return None
    
    @staticmethod
    def save_report(db: Session, report_data: Dict[str, Any]) -> Optional[str]:
        """
        Save report data to database
        
        Args:
            db: Database session
            report_data: Report data dictionary
            
        Returns:
            Report ID if successful, None otherwise
        """
        try:
            # Create report record - handle date type for submitTime
            submit_time = report_data.get('submitTime')
            if isinstance(submit_time, str):
                try:
                    # Try to parse as datetime first, then extract date
                    parsed_datetime = datetime.fromisoformat(submit_time.replace('Z', '+00:00'))
                    submit_date = parsed_datetime.date()
                except ValueError:
                    try:
                        # Try to parse as date directly
                        submit_date = date.fromisoformat(submit_time)
                    except ValueError:
                        # If all fails, use today's date
                        submit_date = date.today()
            elif isinstance(submit_time, datetime):
                submit_date = submit_time.date()
            elif isinstance(submit_time, date):
                submit_date = submit_time
            else:
                submit_date = date.today()
            
            report = DenseReport(
                user=report_data.get('user'),
                doctor=report_data.get('doctor'),
                submitTime=submit_date,
                current_status=report_data.get('current_status', ReportStatus.Checking),
                diagnose=report_data.get('diagnose')
            )
            db.add(report)
            db.flush()  # Get the ID
            
            # Save associated images if provided
            if 'images' in report_data:
                for image_id in report_data['images']:
                    dense_image = DenseImage(
                        report=report.id,
                        image=int(image_id),
                        _type=ImageType.source
                    )
                    db.add(dense_image)
            
            # Save result images if provided
            if 'Result_img' in report_data:
                for image_id in report_data['Result_img']:
                    dense_image = DenseImage(
                        report=report.id,
                        image=int(image_id),
                        _type=ImageType.result
                    )
                    db.add(dense_image)
            
            db.commit()
            return str(report.id)
            
        except Exception as e:
            db.rollback()
            print(f"Error saving report: {e}")
            return None
    
    @staticmethod
    def load_report(db: Session, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Load report data from database
        
        Args:
            db: Database session
            report_id: Report ID
            
        Returns:
            Report data dictionary or None if not found
        """
        try:
            report = db.query(DenseReport).filter(DenseReport.id == int(report_id)).first()
            
            if not report:
                return None
            
            # Get associated images
            source_images = db.query(DenseImage).filter(
                and_(DenseImage.report == report.id, DenseImage._type == ImageType.source)
            ).all()
            
            result_images = db.query(DenseImage).filter(
                and_(DenseImage.report == report.id, DenseImage._type == ImageType.result)
            ).all()
            
            # 处理date类型的submitTime
            if report.submitTime:
                if hasattr(report.submitTime, 'isoformat'):
                    submit_time_str = report.submitTime.isoformat()
                else:
                    submit_time_str = str(report.submitTime)
            else:
                submit_time_str = date.today().isoformat()
            
            return {
                "id": str(report.id),
                "user": report.user,
                "doctor": report.doctor,
                "submitTime": submit_time_str,
                "current_status": report.current_status,
                "diagnose": report.diagnose,
                "images": [str(img.image) for img in source_images],
                "Result_img": [str(img.image) for img in result_images]
            }
            
        except Exception as e:
            print(f"Error loading report: {e}")
            return None
    
    @staticmethod
    def get_user_reports(db: Session, user_id: str, user_type: int) -> List[Dict[str, Any]]:
        """
        Get reports for a user (patient or doctor)
        
        Args:
            db: Database session
            user_id: User ID
            user_type: User type (0 for patient, 1 for doctor)
            
        Returns:
            List of report dictionaries
        """
        try:
            if user_type == 0:  # Patient
                reports = db.query(DenseReport).filter(DenseReport.user == user_id).all()
            else:  # Doctor
                reports = db.query(DenseReport).filter(DenseReport.doctor == user_id).all()
            
            result = []
            for report in reports:
                # Get associated images
                source_images = db.query(DenseImage).filter(
                    and_(DenseImage.report == report.id, DenseImage._type == ImageType.source)
                ).all()
                
                result_images = db.query(DenseImage).filter(
                    and_(DenseImage.report == report.id, DenseImage._type == ImageType.result)
                ).all()
                
                # 处理date类型的submitTime
                if report.submitTime:
                    if hasattr(report.submitTime, 'isoformat'):
                        # 如果是date或datetime对象，都有isoformat方法
                        submit_time_str = report.submitTime.isoformat()
                    else:
                        # 如果是其他类型，转换为字符串
                        submit_time_str = str(report.submitTime)
                else:
                    # 如果没有时间，使用当前日期
                    from datetime import date
                    submit_time_str = date.today().isoformat()
                
                print(f"DEBUG: Report {report.id} submitTime: {report.submitTime} -> {submit_time_str}")
                
                result.append({
                    "id": str(report.id),
                    "user": report.user,
                    "doctor": report.doctor,
                    "submitTime": submit_time_str,
                    "current_status": report.current_status,
                    "diagnose": report.diagnose,
                    "images": [str(img.image) for img in source_images],
                    "Result_img": [str(img.image) for img in result_images]
                })
            
            return result
            
        except Exception as e:
            print(f"Error getting user reports: {e}")
            return []
    
    @staticmethod
    def save_comment(db: Session, report_id: str, comment_data: Dict[str, Any]) -> Optional[str]:
        """
        Save comment data to database
        
        Args:
            db: Database session
            report_id: Report ID
            comment_data: Comment data dictionary
            
        Returns:
            Comment ID if successful, None otherwise
        """
        try:
            comment = Comment(
                report=int(report_id),
                user=comment_data.get('user'),
                content=comment_data.get('content'),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(comment)
            db.flush()  # Get the ID
            
            db.commit()
            return str(comment.id)
            
        except Exception as e:
            db.rollback()
            print(f"Error saving comment: {e}")
            return None
    
    @staticmethod
    def get_report_comments(db: Session, report_id: str) -> List[Dict[str, Any]]:
        """
        Get comments for a report
        
        Args:
            db: Database session
            report_id: Report ID
            
        Returns:
            List of comment dictionaries
        """
        try:
            comments = db.query(Comment).filter(Comment.report == int(report_id)).all()
            
            result = []
            for comment in comments:
                result.append({
                    "id": str(comment.id),
                    "user": comment.user,
                    "content": comment.content,
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat()
                })
            
            return result
            
        except Exception as e:
            print(f"Error getting report comments: {e}")
            return []
    
    @staticmethod
    def update_report_status(db: Session, report_id: str, status: ReportStatus, diagnose: str = None) -> bool:
        """
        Update report status and diagnosis
        
        Args:
            db: Database session
            report_id: Report ID
            status: New status
            diagnose: Diagnosis text (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            report = db.query(DenseReport).filter(DenseReport.id == int(report_id)).first()
            
            if not report:
                return False
            
            report.current_status = status
            if diagnose is not None:
                report.diagnose = diagnose
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error updating report status: {e}")
            return False
    
    @staticmethod
    def delete_report(db: Session, report_id: str) -> bool:
        """
        Delete report and associated data
        
        Args:
            db: Database session
            report_id: Report ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            report = db.query(DenseReport).filter(DenseReport.id == int(report_id)).first()
            
            if not report:
                print(f"Report {report_id} not found")
                return False
            
            report_id_int = int(report_id)
            print(f"Starting deletion process for report {report_id_int}")
            
            # 1. 获取所有关联的dense_image记录
            dense_images = db.query(DenseImage).filter(DenseImage.report == report_id_int).all()
            print(f"Found {len(dense_images)} dense_image records")
            
            # 2. 先处理DenseImage中的result_image引用
            # 获取所有result_image的ID
            result_image_ids = []
            for dense_image in dense_images:
                if dense_image.result_image:
                    result_image_ids.append(dense_image.result_image)
            
            # 3. 删除关联的评论
            print("Deleting comments")
            db.query(Comment).filter(Comment.report == report_id_int).delete()
            
            # 4. 删除dense_image关联表记录 - 必须在删除图片前先删除关联
            print("Deleting dense_image records")
            db.query(DenseImage).filter(DenseImage.report == report_id_int).delete()
            
            # 5. 删除所有result_imgs表中与该报告关联的记录
            print(f"Deleting result images for report {report_id_int}")
            db.query(ResultImage).filter(ResultImage.report_id == report_id_int).delete()
            
            # 6. 删除关联的原始图片
            for dense_image in dense_images:
                if dense_image.image:
                    print(f"Deleting source image {dense_image.image}")
                    image = db.query(Image).filter(Image.id == dense_image.image).first()
                    if image:
                        db.delete(image)
            
            # 7. 最后删除报告本身
            print("Deleting report")
            db.delete(report)
            
            db.commit()
            print(f"Successfully deleted report {report_id}")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error deleting report: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def save_doctor_info(db: Session, doctor_id: str, info: Dict[str, Any]) -> bool:
        """
        Save doctor information to database
        
        Args:
            db: Database session
            doctor_id: Doctor ID
            info: Doctor information dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if doctor record already exists
            doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
            
            if doctor:
                # Update existing record
                for key, value in info.items():
                    if hasattr(doctor, key) and value is not None:
                        setattr(doctor, key, value)
            else:
                # Create new record
                doctor = Doctor(id=doctor_id, **info)
                db.add(doctor)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error saving doctor info: {e}")
            return False
    
    @staticmethod
    def load_doctor_info(db: Session, doctor_id: str) -> Optional[Dict[str, Any]]:
        """
        Load doctor information from database
        
        Args:
            db: Database session
            doctor_id: Doctor ID
            
        Returns:
            Doctor information dictionary or None if not found
        """
        try:
            doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
            
            if not doctor:
                return None
            
            return {
                "id": doctor.id,
                "position": doctor.position,
                "workplace": doctor.workplace,
                "description": doctor.description
            }
            
        except Exception as e:
            print(f"Error loading doctor info: {e}")
            return None
    
    @staticmethod
    def get_report_images(db: Session, report_id: str, image_type: ImageType = None) -> Dict[str, List[str]]:
        """
        Get images associated with a report
        
        Args:
            db: Database session
            report_id: Report ID
            image_type: Optional image type filter
            
        Returns:
            Dictionary with image lists by type
        """
        try:
            query = db.query(DenseImage).filter(DenseImage.report == int(report_id))
            
            if image_type is not None:
                query = query.filter(DenseImage._type == image_type)
            
            images = query.all()
            
            result = {"source": [], "result": []}
            for img in images:
                if img._type == ImageType.source:
                    result["source"].append(str(img.image))
                elif img._type == ImageType.result:
                    result["result"].append(str(img.image))
            
            return result
            
        except Exception as e:
            print(f"Error getting report images: {e}")
            return {"source": [], "result": []}
    
    @staticmethod
    def save_report_image(db: Session, report_id: str, image_id: str, image_type: ImageType) -> bool:
        """
        Associate an image with a report
        
        Args:
            db: Database session
            report_id: Report ID
            image_id: Image ID
            image_type: Type of image (source or result)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            dense_image = DenseImage(
                report=int(report_id),
                image=int(image_id),
                _type=image_type
            )
            db.add(dense_image)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error saving report image: {e}")
            return False
    
    # Avatar management methods
    @staticmethod
    def save_avatar(db: Session, user_id: str, avatar_data: bytes, filename: str, format: str = "jpg") -> Optional[str]:
        """
        Save user avatar to database
        
        Args:
            db: Database session
            user_id: User ID
            avatar_data: Avatar binary data
            filename: Original filename
            format: Image format
            
        Returns:
            Avatar ID if successful, None otherwise
        """
        try:
            # Check if user already has an avatar
            existing_avatar = db.query(Avatar).filter(Avatar.user_id == user_id).first()
            
            if existing_avatar:
                # Update existing avatar
                existing_avatar.filename = filename
                existing_avatar.data = avatar_data
                existing_avatar.format = format
                existing_avatar.file_size = len(avatar_data)
                existing_avatar.upload_time = datetime.now()
                avatar_id = existing_avatar.id
            else:
                # Create new avatar
                avatar = Avatar(
                    user_id=user_id,
                    filename=filename,
                    data=avatar_data,
                    format=format,
                    file_size=len(avatar_data),
                    upload_time=datetime.now()
                )
                db.add(avatar)
                db.flush()  # Get the ID
                avatar_id = avatar.id
            
            db.commit()
            return str(avatar_id)
            
        except Exception as e:
            db.rollback()
            print(f"Error saving avatar: {e}")
            return None
    
    @staticmethod
    def load_avatar(db: Session, user_id: str) -> Optional[bytes]:
        """
        Load user avatar from database
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Avatar binary data or None if not found
        """
        try:
            avatar = db.query(Avatar).filter(Avatar.user_id == user_id).first()
            
            if not avatar:
                return None
            
            return avatar.data
            
        except Exception as e:
            print(f"Error loading avatar: {e}")
            return None
    
    @staticmethod
    def get_avatar_info(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get avatar information for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Avatar information dictionary or None if not found
        """
        try:
            avatar = db.query(Avatar).filter(Avatar.user_id == user_id).first()
            
            if not avatar:
                return None
            
            return {
                "id": str(avatar.id),
                "user_id": avatar.user_id,
                "filename": avatar.filename,
                "format": avatar.format,
                "file_size": avatar.file_size,
                "upload_time": avatar.upload_time.isoformat()
            }
            
        except Exception as e:
            print(f"Error getting avatar info: {e}")
            return None
    
    # Result image management methods
    @staticmethod
    def save_result_image(db: Session, report_id: str, image_data: bytes, filename: str, format: str = "jpg") -> Optional[str]:
        """
        Save result image to database
        
        Args:
            db: Database session
            report_id: Report ID
            image_data: Image binary data
            filename: Original filename
            format: Image format
            
        Returns:
            Result image ID if successful, None otherwise
        """
        try:
            result_image = ResultImage(
                report_id=int(report_id),
                filename=filename,
                data=image_data,
                format=format,
                file_size=len(image_data),
                created_time=datetime.now()
            )
            db.add(result_image)
            db.flush()  # Get the ID
            
            # Update or create dense_image record to associate result image
            dense_image = db.query(DenseImage).filter(
                DenseImage.report == int(report_id),
                DenseImage._type == ImageType.result
            ).first()
            
            if dense_image:
                # Update existing record
                dense_image.result_image = result_image.id
            else:
                # Create new dense_image record
                new_dense_image = DenseImage(
                    report=int(report_id),
                    result_image=result_image.id,
                    _type=ImageType.result
                )
                db.add(new_dense_image)
            
            db.commit()
            return str(result_image.id)
            
        except Exception as e:
            db.rollback()
            print(f"Error saving result image: {e}")
            return None
    
    @staticmethod
    def load_result_image(db: Session, result_image_id: str) -> Optional[bytes]:
        """
        Load result image from database
        
        Args:
            db: Database session
            result_image_id: Result image ID
            
        Returns:
            Result image binary data or None if not found
        """
        try:
            # 验证图片ID是否有效
            if not result_image_id or result_image_id.lower() in ['none', 'null', '']:
                print(f"Invalid result image ID: {result_image_id}")
                return None
            
            # 尝试转换为整数
            try:
                image_id_int = int(result_image_id)
            except (ValueError, TypeError) as e:
                print(f"Cannot convert result image ID to int: {result_image_id}, error: {e}")
                return None
            
            result_image = db.query(ResultImage).filter(ResultImage.id == image_id_int).first()
            
            if not result_image:
                print(f"Result image not found for ID: {image_id_int}")
                return None
            
            return result_image.data
            
        except Exception as e:
            print(f"Error loading result image: {e}")
            return None
    
    @staticmethod
    def get_report_result_images(db: Session, report_id: str) -> List[Dict[str, Any]]:
        """
        Get all result images for a report
        
        Args:
            db: Database session
            report_id: Report ID
            
        Returns:
            List of result image dictionaries
        """
        try:
            result_images = db.query(ResultImage).filter(ResultImage.report_id == int(report_id)).all()
            
            result = []
            for img in result_images:
                result.append({
                    "id": str(img.id),
                    "report_id": str(img.report_id),
                    "filename": img.filename,
                    "format": img.format,
                    "file_size": img.file_size,
                    "created_time": img.created_time.isoformat()
                })
            
            return result
            
        except Exception as e:
            print(f"Error getting report result images: {e}")
            return []
    
    @staticmethod
    def delete_avatar(db: Session, user_id: str) -> bool:
        """
        Delete user avatar
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            avatar = db.query(Avatar).filter(Avatar.user_id == user_id).first()
            
            if not avatar:
                return False
            
            db.delete(avatar)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error deleting avatar: {e}")
            return False
    
    @staticmethod
    def delete_result_image(db: Session, result_image_id: str) -> bool:
        """
        Delete result image and its associations
        
        Args:
            db: Database session
            result_image_id: Result image ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result_image = db.query(ResultImage).filter(ResultImage.id == int(result_image_id)).first()
            
            if not result_image:
                return False
            
            # Remove associations in dense_image table
            db.query(DenseImage).filter(DenseImage.result_image == int(result_image_id)).update({"result_image": None})
            
            # Delete the result image
            db.delete(result_image)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error deleting result image: {e}")
            return False