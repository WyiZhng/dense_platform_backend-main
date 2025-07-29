"""
Admin Dashboard API

This module provides API endpoints for the admin dashboard,
including system statistics, user analytics, and system health monitoring.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel
from datetime import datetime, timedelta, date

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.services.rbac_middleware import RequirePermission
from dense_platform_backend_main.utils.response import success_response, error_response
from dense_platform_backend_main.database.table import (
    User, UserDetail, Doctor, DenseReport, Comment, AuditLog, UserSession,
    UserType, ReportStatus
)
#自己改了这个
router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard"])


@router.get("/stats/overview")
async def get_system_overview(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get system overview statistics
    
    Requires: admin:system permission
    """
    try:
        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        total_patients = db.query(User).filter(User.type == UserType.Patient).count()
        total_doctors = db.query(User).filter(User.type == UserType.Doctor).count()
        
        # Report statistics
        total_reports = db.query(DenseReport).count()
        pending_reports = db.query(DenseReport).filter(
            DenseReport.current_status == ReportStatus.Checking
        ).count()
        completed_reports = db.query(DenseReport).filter(
            DenseReport.current_status == ReportStatus.Completed
        ).count()
        abnormal_reports = db.query(DenseReport).filter(
            DenseReport.current_status == ReportStatus.Abnormality
        ).count()
        
        # Recent activity (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        new_users_today = db.query(User).filter(User.created_at >= yesterday).count()
        new_reports_today = db.query(DenseReport).filter(
            DenseReport.submitTime >= yesterday.date()
        ).count()
        
        # Active sessions
        active_sessions = db.query(UserSession).filter(
            and_(
                UserSession.is_active == True,
                UserSession.expires_at > datetime.now()
            )
        ).count()
        
        return success_response(
            data={
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "patients": total_patients,
                    "doctors": total_doctors,
                    "new_today": new_users_today
                },
                "reports": {
                    "total": total_reports,
                    "pending": pending_reports,
                    "completed": completed_reports,
                    "abnormal": abnormal_reports,
                    "new_today": new_reports_today
                },
                "system": {
                    "active_sessions": active_sessions
                }
            },
            message="System overview retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve system overview: {str(e)}")


@router.get("/stats/users")
async def get_user_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Get detailed user statistics
    
    Requires: admin:users permission
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        # User registration trends
        user_registrations = db.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date
        ).group_by(
            func.date(User.created_at)
        ).order_by(
            func.date(User.created_at)
        ).all()
        
        # User type distribution
        user_type_stats = db.query(
            User.type,
            func.count(User.id).label('count')
        ).group_by(User.type).all()
        
        # Active vs inactive users
        active_stats = db.query(
            User.is_active,
            func.count(User.id).label('count')
        ).group_by(User.is_active).all()
        
        # Recent logins (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_logins = db.query(
            func.date(User.last_login).label('date'),
            func.count(User.id).label('count')
        ).filter(
            and_(
                User.last_login >= week_ago,
                User.last_login.isnot(None)
            )
        ).group_by(
            func.date(User.last_login)
        ).order_by(
            func.date(User.last_login)
        ).all()
        
        return success_response(
            data={
                "registration_trend": [
                    {"date": reg.date.isoformat(), "count": reg.count}
                    for reg in user_registrations
                ],
                "user_type_distribution": [
                    {"type": stat.type.name, "count": stat.count}
                    for stat in user_type_stats
                ],
                "active_distribution": [
                    {"status": "active" if stat.is_active else "inactive", "count": stat.count}
                    for stat in active_stats
                ],
                "recent_logins": [
                    {"date": login.date.isoformat(), "count": login.count}
                    for login in recent_logins
                ]
            },
            message="User statistics retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve user statistics: {str(e)}")


@router.get("/stats/reports")
async def get_report_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get detailed report statistics
    
    Requires: admin:system permission
    """
    try:
        start_date = datetime.now().date() - timedelta(days=days)
        
        # Report submission trends
        report_submissions = db.query(
            DenseReport.submitTime.label('date'),
            func.count(DenseReport.id).label('count')
        ).filter(
            DenseReport.submitTime >= start_date
        ).group_by(
            DenseReport.submitTime
        ).order_by(
            DenseReport.submitTime
        ).all()
        
        # Report status distribution
        status_stats = db.query(
            DenseReport.current_status,
            func.count(DenseReport.id).label('count')
        ).group_by(DenseReport.current_status).all()
        
        # Reports by doctor (top 10)
        doctor_stats = db.query(
            DenseReport.doctor,
            func.count(DenseReport.id).label('count'),
            UserDetail.name
        ).join(
            UserDetail, DenseReport.doctor == UserDetail.id, isouter=True
        ).filter(
            DenseReport.doctor.isnot(None)
        ).group_by(
            DenseReport.doctor
        ).order_by(
            func.count(DenseReport.id).desc()
        ).limit(10).all()
        
        # Average processing time (for completed reports)
        avg_processing_time = db.query(
            func.avg(
                func.datediff(
                    func.current_date(),
                    DenseReport.submitTime
                )
            ).label('avg_days')
        ).filter(
            DenseReport.current_status.in_([ReportStatus.Completed, ReportStatus.Abnormality])
        ).scalar()
        
        return success_response(
            data={
                "submission_trend": [
                    {"date": sub.date.isoformat(), "count": sub.count}
                    for sub in report_submissions
                ],
                "status_distribution": [
                    {"status": stat.current_status.name, "count": stat.count}
                    for stat in status_stats
                ],
                "top_doctors": [
                    {
                        "doctor_id": stat.doctor,
                        "doctor_name": stat.name or "Unknown",
                        "report_count": stat.count
                    }
                    for stat in doctor_stats
                ],
                "avg_processing_days": round(avg_processing_time or 0, 2)
            },
            message="Report statistics retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve report statistics: {str(e)}")


@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = Query(50, ge=1, le=200, description="Number of activities to retrieve"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    Get recent system activity from audit logs
    
    Requires: admin:audit permission
    """
    try:
        recent_activities = db.query(AuditLog).join(
            User, AuditLog.user_id == User.id, isouter=True
        ).join(
            UserDetail, User.id == UserDetail.id, isouter=True
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()
        
        activities = []
        for activity in recent_activities:
            user_name = "Unknown"
            if activity.user and activity.user.user_detail:
                user_name = activity.user.user_detail.name or activity.user.id
            elif activity.user:
                user_name = activity.user.id
            
            activity_data = {
                "id": activity.id,
                "user_id": activity.user_id,
                "user_name": user_name,
                "action": activity.action,
                "resource_type": activity.resource_type,
                "resource_id": activity.resource_id,
                "timestamp": activity.timestamp,
                "success": activity.success,
                "error_message": activity.error_message
            }
            activities.append(activity_data)
        
        return success_response(
            data={"activities": activities},
            message="Recent activity retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve recent activity: {str(e)}")


@router.get("/system/health")
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get system health status
    
    Requires: admin:system permission
    """
    try:
        # Database connectivity check
        db_status = "healthy"
        try:
            db.execute("SELECT 1")
        except Exception:
            db_status = "unhealthy"
        
        # Check for expired sessions
        expired_sessions = db.query(UserSession).filter(
            and_(
                UserSession.is_active == True,
                UserSession.expires_at < datetime.now()
            )
        ).count()
        
        # Check for stale reports (pending for more than 7 days)
        week_ago = datetime.now().date() - timedelta(days=7)
        stale_reports = db.query(DenseReport).filter(
            and_(
                DenseReport.current_status == ReportStatus.Checking,
                DenseReport.submitTime < week_ago
            )
        ).count()
        
        # Check recent errors in audit log
        hour_ago = datetime.now() - timedelta(hours=1)
        recent_errors = db.query(AuditLog).filter(
            and_(
                AuditLog.success == False,
                AuditLog.timestamp >= hour_ago
            )
        ).count()
        
        # Overall health assessment
        health_issues = []
        if db_status != "healthy":
            health_issues.append("Database connectivity issues")
        if expired_sessions > 0:
            health_issues.append(f"{expired_sessions} expired sessions need cleanup")
        if stale_reports > 10:
            health_issues.append(f"{stale_reports} reports pending for over 7 days")
        if recent_errors > 5:
            health_issues.append(f"{recent_errors} errors in the last hour")
        
        overall_status = "healthy" if not health_issues else "warning"
        if db_status != "healthy" or recent_errors > 20:
            overall_status = "critical"
        
        return success_response(
            data={
                "overall_status": overall_status,
                "database_status": db_status,
                "issues": health_issues,
                "metrics": {
                    "expired_sessions": expired_sessions,
                    "stale_reports": stale_reports,
                    "recent_errors": recent_errors
                },
                "last_checked": datetime.now().isoformat()
            },
            message="System health status retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve system health: {str(e)}")


@router.get("/reports/pending")
async def get_pending_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get pending reports that need attention
    
    Requires: admin:system permission
    """
    try:
        # Get total count
        total_count = db.query(DenseReport).filter(
            DenseReport.current_status == ReportStatus.Checking
        ).count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        pending_reports = db.query(DenseReport).join(
            UserDetail, DenseReport.user == UserDetail.id, isouter=True
        ).filter(
            DenseReport.current_status == ReportStatus.Checking
        ).order_by(
            DenseReport.submitTime.asc()
        ).offset(offset).limit(page_size).all()
        
        # Format response
        reports = []
        for report in pending_reports:
            patient_name = "Unknown"
            if report.user2 and report.user2.user_detail:
                patient_name = report.user2.user_detail.name or report.user2.id
            
            doctor_name = "Unassigned"
            if report.user1 and report.user1.user_detail:
                doctor_name = report.user1.user_detail.name or report.user1.id
            
            days_pending = (datetime.now().date() - report.submitTime).days
            
            report_data = {
                "id": report.id,
                "patient_id": report.user,
                "patient_name": patient_name,
                "doctor_id": report.doctor,
                "doctor_name": doctor_name,
                "submit_time": report.submitTime,
                "days_pending": days_pending,
                "status": report.current_status.name
            }
            reports.append(report_data)
        
        return success_response(
            data={
                "reports": reports,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size
                }
            },
            message="Pending reports retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve pending reports: {str(e)}")


@router.post("/maintenance/cleanup-sessions")
async def cleanup_expired_sessions(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Clean up expired sessions
    
    Requires: admin:system permission
    """
    try:
        # Find expired sessions
        expired_sessions = db.query(UserSession).filter(
            and_(
                UserSession.is_active == True,
                UserSession.expires_at < datetime.now()
            )
        ).all()
        
        count = len(expired_sessions)
        
        # Deactivate expired sessions
        for session in expired_sessions:
            session.is_active = False
        
        # Create audit log
        from dense_platform_backend_main.database.table import AuditLog
        import json
        
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="cleanup_expired_sessions",
            resource_type="system",
            resource_id="sessions",
            new_values=json.dumps({"cleaned_sessions": count}),
            success=True
        )
        db.add(audit_log)
        
        db.commit()
        
        return success_response(
            data={"cleaned_sessions": count},
            message=f"Successfully cleaned up {count} expired sessions"
        )
        
    except Exception as e:
        db.rollback()
        return error_response(message=f"Failed to cleanup sessions: {str(e)}")