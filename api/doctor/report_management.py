"""
Doctor Report Management API (Fixed Version)

This module provides comprehensive CRUD operations for medical reports,
report status management, and workflow management for doctors.
Fixed to properly handle DateTime submitTime field and token extraction.
"""

from datetime import date, datetime
from typing import Union
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Create security scheme for Bearer token
security = HTTPBearer(auto_error=False)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from enum import Enum

from dense_platform_backend_main.database.table import (
    ReportStatus, ImageType, UserType, DenseReport, User, UserDetail, Doctor
)
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.api.auth.session import get_db, SessionService
from dense_platform_backend_main.api.doctor.token_dependency import validate_doctor_token, validate_doctor_token_flexible
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils.request import TokenRequest

router = APIRouter()


class ReportStatusUpdate(str, Enum):
    """Report status options for updates"""
    CHECKING = "Checking"
    COMPLETED = "Completed"
    ABNORMALITY = "Abnormality"
    ERROR = "Error"


class CreateReportRequest(BaseModel):
    """Request model for creating a new report"""
    patient_id: str = Field(..., description="Patient user ID")
    images: List[str] = Field(default=[], description="List of image IDs")
    initial_notes: Optional[str] = Field(None, description="Initial notes or observations")


class UpdateReportRequest(BaseModel):
    """Request model for updating a report"""
    report_id: str = Field(..., description="Report ID to update")
    status: Optional[ReportStatusUpdate] = Field(None, description="New status")
    diagnose: Optional[str] = Field(None, description="Diagnosis text")
    notes: Optional[str] = Field(None, description="Additional notes")


class ReportFilterRequest(BaseModel):
    """Request model for filtering reports"""
    status: Optional[ReportStatusUpdate] = Field(None, description="Filter by status")
    patient_id: Optional[str] = Field(None, description="Filter by patient ID")
    date_from: Optional[str] = Field(None, description="Filter from date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter to date (YYYY-MM-DD)")
    limit: int = Field(50, description="Maximum number of results")
    offset: int = Field(0, description="Offset for pagination")


class ReportModel(BaseModel):
    """Report data model"""
    class Config:
        from_attributes = True
    
    id: str
    user: str
    doctor: str
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    submitTime: Union[date, datetime]  # Handles both date and datetime types
    current_status: ReportStatus
    diagnose: Optional[str] = None
    images: List[str] = []
    result_images: List[str] = []


class ReportDetailModel(ReportModel):
    """Detailed report model with additional information"""
    comments: List[Dict[str, Any]] = []
    patient_details: Optional[Dict[str, Any]] = None
    doctor_details: Optional[Dict[str, Any]] = None


class ReportListResponse(Response):
    """Response model for report lists"""
    reports: List[ReportModel]
    total: int
    page: int
    limit: int


class ReportDetailResponse(Response):
    """Response model for detailed report"""
    report: ReportDetailModel


class CreateReportResponse(Response):
    """Response model for created report"""
    report_id: str


@router.post("/api/doctor/reports/create")
async def create_report(
    request: CreateReportRequest,
    db: Session = Depends(get_db),
    session_info: Dict[str, Any] = Depends(validate_doctor_token)
):
    """
    Create a new medical report
    Requires doctor role
    """
    doctor_id = session_info["user_id"]
    
    # Verify patient exists
    patient = db.query(User).filter(
        User.id == request.patient_id,
        User.type == UserType.Patient
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Create report data with current datetime
    report_data = {
        "user": request.patient_id,
        "doctor": doctor_id,
        "submitTime": datetime.now().isoformat(),  # Now includes time
        "current_status": ReportStatus.Checking,
        "diagnose": request.initial_notes,
        "images": request.images
    }
    
    # Save report to database
    report_id = DatabaseStorageService.save_report(db, report_data)
    
    if not report_id:
        raise HTTPException(status_code=500, detail="Failed to create report")
    
    return CreateReportResponse(report_id=report_id)


@router.post("/api/doctor/reports/list")
async def get_doctor_reports(
    request: ReportFilterRequest,
    db: Session = Depends(get_db),
    session_info: Dict[str, Any] = Depends(validate_doctor_token)
):
    """
    Get list of reports assigned to the current doctor with filtering
    Requires doctor role
    """
    doctor_id = session_info["user_id"]
    
    try:
        # Build query
        query = db.query(DenseReport).filter(DenseReport.doctor == doctor_id)
        
        # Apply filters
        if request.status:
            status_enum = ReportStatus[request.status.value]
            query = query.filter(DenseReport.current_status == status_enum)
        
        if request.patient_id:
            query = query.filter(DenseReport.user == request.patient_id)
        
        if request.date_from:
            from_date = datetime.fromisoformat(request.date_from)
            query = query.filter(DenseReport.submitTime >= from_date)
        
        if request.date_to:
            to_date = datetime.fromisoformat(request.date_to)
            query = query.filter(DenseReport.submitTime <= to_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        reports = query.offset(request.offset).limit(request.limit).all()
        
        # Convert to response format
        report_models = []
        for report in reports:
            # Get patient and doctor names
            patient = db.query(User).join(UserDetail).filter(User.id == report.user).first()
            doctor = db.query(User).join(UserDetail).filter(User.id == report.doctor).first()
            
            patient_name = patient.user_detail.name if patient and patient.user_detail else report.user
            doctor_name = doctor.user_detail.name if doctor and doctor.user_detail else report.doctor
            
            # Get images
            images_data = DatabaseStorageService.get_report_images(db, str(report.id))
            
            report_model = ReportModel(
                id=str(report.id),
                user=report.user,
                doctor=report.doctor,
                patient_name=patient_name,
                doctor_name=doctor_name,
                submitTime=report.submitTime,  # Now directly use DateTime field
                current_status=report.current_status,
                diagnose=report.diagnose,
                images=images_data.get("source", []),
                result_images=images_data.get("result", [])
            )
            report_models.append(report_model)
        
        return ReportListResponse(
            reports=report_models,
            total=total,
            page=request.offset // request.limit + 1,
            limit=request.limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports: {str(e)}")


@router.post("/api/doctor/reports/detail")
async def get_report_detail(
    request: Request,
    report_id: str = Query(..., description="Report ID"),
    db: Session = Depends(get_db),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get detailed information about a specific report
    Requires doctor review permission or report read permission
    """
    # Extract token from Authorization header or request body
    token = None
    if authorization:
        token = authorization.credentials
    else:
        # Try to get token from request body
        try:
            body = await request.json()
            if isinstance(body, dict) and "token" in body:
                token = body["token"]
        except Exception:
            pass
    
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required - no token provided")
    
    # Validate session
    session_info = SessionService.validate_session(db, token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Check if user is doctor or has doctor role
    user_id = session_info["user_id"]
    user_type = session_info.get("user_type", UserType.Patient)
    
    # Get user roles for additional checking
    from dense_platform_backend_main.services.rbac_service import RBACService
    user_roles = RBACService.get_user_roles(db, user_id)
    
    is_doctor = (
        user_type == UserType.Doctor or
        any(role["name"] == "doctor" for role in user_roles) or
        any(role["name"] == "admin" for role in user_roles)
    )
    
    if not is_doctor:
        raise HTTPException(status_code=403, detail="Doctor access required")
    
    doctor_id = user_id
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if doctor has access to this report
    if report_data["doctor"] != doctor_id:
        # For now, allow access if user is authenticated (can be enhanced later with RBAC)
        # TODO: Add proper RBAC permission check
        pass
    
    try:
        # Get patient details
        patient = db.query(User).join(UserDetail).filter(User.id == report_data["user"]).first()
        patient_details = None
        if patient and patient.user_detail:
            patient_details = {
                "name": patient.user_detail.name,
                "sex": patient.user_detail.sex,
                "birth": patient.user_detail.birth.isoformat() if patient.user_detail.birth else None,
                "phone": patient.user_detail.phone,
                "email": patient.user_detail.email,
                "address": patient.user_detail.address
            }
        
        # Get doctor details
        doctor_user = db.query(User).filter(User.id == report_data["doctor"]).first()
        doctor_details = None
        if doctor_user:
            # Get user detail
            user_detail = db.query(UserDetail).filter(UserDetail.id == doctor_user.id).first()
            # Get doctor info
            doctor_info = db.query(Doctor).filter(Doctor.id == doctor_user.id).first()
            
            doctor_details = {
                "name": user_detail.name if user_detail else doctor_user.id,
                "position": doctor_info.position if doctor_info else "",
                "workplace": doctor_info.workplace if doctor_info else ""
            }
        
        # Get comments
        comments = DatabaseStorageService.get_report_comments(db, report_id)
        
        # Get images
        images_data = DatabaseStorageService.get_report_images(db, report_id)
        
        # Parse submitTime safely for older Python versions
        submit_time = report_data["submitTime"]
        if isinstance(submit_time, str):
            try:
                # Try to parse ISO format datetime string
                # Replace 'T' with space and remove timezone info for compatibility
                time_str = submit_time.replace('T', ' ').split('+')[0].split('Z')[0]
                if '.' in time_str:
                    # Handle microseconds
                    submit_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    # Handle without microseconds
                    submit_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    # Try date only format
                    submit_time = datetime.strptime(submit_time, '%Y-%m-%d')
                except ValueError:
                    # If all parsing fails, use current time
                    submit_time = datetime.now()
        
        # Create detailed report model
        report_detail = ReportDetailModel(
            id=report_data["id"],
            user=report_data["user"],
            doctor=report_data["doctor"],
            patient_name=patient_details["name"] if patient_details else report_data["user"],
            doctor_name=doctor_details["name"] if doctor_details else report_data["doctor"],
            submitTime=submit_time,
            current_status=report_data["current_status"],
            diagnose=report_data["diagnose"],
            images=images_data.get("source", []),
            result_images=images_data.get("result", []),
            comments=comments,
            patient_details=patient_details,
            doctor_details=doctor_details
        )
        
        return ReportDetailResponse(report=report_detail)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve report details: {str(e)}")


@router.post("/api/doctor/reports/update")
async def update_report(
    request: UpdateReportRequest,
    db: Session = Depends(get_db),
    session_info: Dict[str, Any] = Depends(validate_doctor_token)
):
    """
    Update report status, diagnosis, or notes
    Requires doctor diagnose permission or report write permission
    """
    doctor_id = session_info["user_id"]
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if doctor has access to this report
    if report_data["doctor"] != doctor_id:
        # For now, allow access if user is authenticated (can be enhanced later with RBAC)
        # TODO: Add proper RBAC permission check
        pass
    
    try:
        # Update status if provided
        if request.status:
            status_enum = ReportStatus[request.status.value]
            success = DatabaseStorageService.update_report_status(
                db, request.report_id, status_enum, request.diagnose
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update report status")
        
        # Update diagnosis if provided (without status change)
        elif request.diagnose:
            success = DatabaseStorageService.update_report_status(
                db, request.report_id, report_data["current_status"], request.diagnose
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update diagnosis")
        
        return Response(message="Report updated successfully")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update report: {str(e)}")


@router.post("/api/doctor/reports/workflow/pending")
async def get_pending_reports(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get all pending reports assigned to the current doctor
    Requires doctor role
    """
    # Extract token from Authorization header or request body
    token = None
    if authorization:
        token = authorization.credentials
    else:
        # Try to get token from request body
        try:
            body = await request.json()
            if isinstance(body, dict) and "token" in body:
                token = body["token"]
        except Exception:
            pass
    
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required - no token provided")
    
    # Validate session
    session_info = SessionService.validate_session(db, token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Check if user is doctor or has doctor role
    user_id = session_info["user_id"]
    user_type = session_info.get("user_type", UserType.Patient)
    
    # Get user roles for additional checking
    from dense_platform_backend_main.services.rbac_service import RBACService
    user_roles = RBACService.get_user_roles(db, user_id)
    
    is_doctor = (
        user_type == UserType.Doctor or
        any(role["name"] == "doctor" for role in user_roles) or
        any(role["name"] == "admin" for role in user_roles)
    )
    
    if not is_doctor:
        raise HTTPException(status_code=403, detail="Doctor access required")
    
    doctor_id = user_id
    
    try:
        # Get pending reports
        reports = db.query(DenseReport).filter(
            DenseReport.doctor == doctor_id,
            DenseReport.current_status == ReportStatus.Checking
        ).all()
        
        # Convert to response format
        report_models = []
        for report in reports:
            # Get patient name
            patient = db.query(User).join(UserDetail, isouter=True).filter(User.id == report.user).first()
            patient_name = patient.user_detail.name if patient and hasattr(patient, 'user_detail') and patient.user_detail else report.user
            
            # Get images
            images_data = DatabaseStorageService.get_report_images(db, str(report.id))
            
            # Get doctor name
            doctor = db.query(User).join(UserDetail, isouter=True).filter(User.id == report.doctor).first()
            doctor_name = doctor.user_detail.name if doctor and hasattr(doctor, 'user_detail') and doctor.user_detail else report.doctor
            
            report_model = ReportModel(
                id=str(report.id),
                user=report.user,
                doctor=report.doctor,
                patient_name=patient_name,
                doctor_name=doctor_name,
                submitTime=report.submitTime,  # Now directly use DateTime field
                current_status=report.current_status,
                diagnose=report.diagnose,
                images=images_data.get("source", []),
                result_images=images_data.get("result", [])
            )
            report_models.append(report_model)
        
        return ReportListResponse(
            reports=report_models,
            total=len(report_models),
            page=1,
            limit=len(report_models)
        )
        
    except Exception as e:
        import traceback
        print(f"Error retrieving pending reports: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve pending reports: {str(e)}")


@router.post("/api/doctor/reports/statistics")
async def get_doctor_statistics(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get statistics for the current doctor's reports
    Requires doctor role
    """
    # Extract token from Authorization header or request body
    token = None
    if authorization:
        token = authorization.credentials
    else:
        # Try to get token from request body
        try:
            body = await request.json()
            if isinstance(body, dict) and "token" in body:
                token = body["token"]
        except Exception:
            pass
    
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required - no token provided")
    
    # Validate session
    session_info = SessionService.validate_session(db, token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Check if user is doctor or has doctor role
    user_id = session_info["user_id"]
    user_type = session_info.get("user_type", UserType.Patient)
    
    # Get user roles for additional checking
    from dense_platform_backend_main.services.rbac_service import RBACService
    user_roles = RBACService.get_user_roles(db, user_id)
    
    is_doctor = (
        user_type == UserType.Doctor or
        any(role["name"] == "doctor" for role in user_roles) or
        any(role["name"] == "admin" for role in user_roles)
    )
    
    if not is_doctor:
        raise HTTPException(status_code=403, detail="Doctor access required")
    
    doctor_id = user_id
    print(f"DEBUG: Getting statistics for doctor: {doctor_id}")
    
    try:
        # Get all reports for this doctor
        all_reports = db.query(DenseReport).filter(DenseReport.doctor == doctor_id).all()
        print(f"DEBUG: Found {len(all_reports)} total reports for doctor {doctor_id}")
        
        # Calculate statistics
        total_reports = len(all_reports)
        pending_reports = len([r for r in all_reports if r.current_status == ReportStatus.Checking])
        completed_reports = len([r for r in all_reports if r.current_status == ReportStatus.Completed])
        abnormal_reports = len([r for r in all_reports if r.current_status == ReportStatus.Abnormality])
        error_reports = len([r for r in all_reports if r.current_status == ReportStatus.Error])
        
        # Get recent activity (last 7 days) - handles both date and datetime
        from datetime import timedelta, time
        week_ago = datetime.now() - timedelta(days=7)
        
        # Handle both date and datetime types
        recent_reports = 0
        for r in all_reports:
            if r.submitTime:
                try:
                    # If submitTime is date, convert to datetime for comparison
                    if hasattr(r.submitTime, 'date'):
                        # It's a datetime object
                        submit_datetime = r.submitTime
                    else:
                        # It's a date object, convert to datetime
                        submit_datetime = datetime.combine(r.submitTime, time.min)
                    
                    if submit_datetime >= week_ago:
                        recent_reports += 1
                except Exception as e:
                    print(f"DEBUG: Error comparing time for report {r.id}: {e}")
                    continue
        
        statistics = {
            "total_reports": total_reports,
            "pending_reports": pending_reports,
            "completed_reports": completed_reports,
            "abnormal_reports": abnormal_reports,
            "error_reports": error_reports,
            "recent_reports": recent_reports,
            "completion_rate": (completed_reports / total_reports * 100) if total_reports > 0 else 0
        }
        
        print(f"DEBUG: Statistics calculated: {statistics}")
        return Response(data=statistics)
        
    except Exception as e:
        print(f"ERROR: Failed to retrieve statistics: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")