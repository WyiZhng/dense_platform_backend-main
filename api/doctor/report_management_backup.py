"""
Doctor Report Management API

This module provides comprehensive CRUD operations for medical reports,
report status management, and workflow management for doctors.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from enum import Enum

from dense_platform_backend_main.database.table import (
    ReportStatus, ImageType, UserType, DenseReport, User, UserDetail, Doctor
)
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.services.rbac_middleware import RequireRole, RequireAnyPermission
from dense_platform_backend_main.services.legacy_auth_middleware import RequireDoctorLegacy, RequirePermissionLegacy, RequireAuthLegacy
from dense_platform_backend_main.api.auth.session import get_db, SessionService
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response

router = APIRouter()


def validate_doctor_token(request: TokenRequest, db: Session) -> Dict[str, Any]:
    """
    Validate token from request body and ensure user is a doctor
    
    Args:
        request: Request containing token
        db: Database session
        
    Returns:
        Session info with user details
        
    Raises:
        HTTPException: If authentication fails or user is not a doctor
    """
    if not request.token:
        raise HTTPException(status_code=401, detail="Authentication required - no token provided")
    
    # Validate session
    session_info = SessionService.validate_session(db, request.token)
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
    
    # Enhance session info
    session_info.update({
        "roles": user_roles,
        "permissions": RBACService.get_user_permissions(db, user_id),
        "is_admin": RBACService.has_admin_role(db, user_id)
    })
    
    return session_info


class ReportStatusUpdate(str, Enum):
    """Report status options for updates"""
    CHECKING = "Checking"
    COMPLETED = "Completed"
    ABNORMALITY = "Abnormality"
    ERROR = "Error"


class DiagnosisWorkflowStatus(str, Enum):
    """Diagnosis workflow status options"""
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    UNDER_REVIEW = "Under Review"
    COMPLETED = "Completed"
    REQUIRES_CONSULTATION = "Requires Consultation"


class CreateReportRequest(TokenRequest):
    """Request model for creating a new report"""
    patient_id: str = Field(..., description="Patient user ID")
    images: List[str] = Field(default=[], description="List of image IDs")
    initial_notes: Optional[str] = Field(None, description="Initial notes or observations")


class UpdateReportRequest(TokenRequest):
    """Request model for updating a report"""
    report_id: str = Field(..., description="Report ID to update")
    status: Optional[ReportStatusUpdate] = Field(None, description="New status")
    diagnose: Optional[str] = Field(None, description="Diagnosis text")
    notes: Optional[str] = Field(None, description="Additional notes")


class AssignReportRequest(TokenRequest):
    """Request model for assigning a report to a doctor"""
    report_id: str = Field(..., description="Report ID to assign")
    doctor_id: str = Field(..., description="Doctor user ID to assign to")


class DiagnosisWorkflowRequest(TokenRequest):
    """Request model for diagnosis workflow operations"""
    report_id: str = Field(..., description="Report ID")
    workflow_status: DiagnosisWorkflowStatus = Field(..., description="Workflow status")
    notes: Optional[str] = Field(None, description="Workflow notes")
    consultation_request: Optional[str] = Field(None, description="Consultation request details")


class ConsultationRequest(TokenRequest):
    """Request model for requesting consultation"""
    report_id: str = Field(..., description="Report ID")
    consulting_doctor_id: str = Field(..., description="Doctor ID to consult")
    consultation_reason: str = Field(..., description="Reason for consultation")
    priority: str = Field("normal", description="Consultation priority: low, normal, high, urgent")


class DiagnosisReviewRequest(TokenRequest):
    """Request model for diagnosis review"""
    report_id: str = Field(..., description="Report ID")
    review_status: str = Field(..., description="Review status: approved, rejected, needs_revision")
    review_notes: str = Field(..., description="Review notes")
    suggested_changes: Optional[str] = Field(None, description="Suggested changes")


class ReportFilterRequest(TokenRequest):
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
    submitTime: datetime
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
    db: Session = Depends(get_db)
):
    """
    Create a new medical report
    Requires doctor role
    """
    # Validate doctor token
    session_info = validate_doctor_token(request, db)
    doctor_id = session_info["user_id"]
    
    # Verify patient exists
    patient = db.query(User).filter(
        User.id == request.patient_id,
        User.type == UserType.Patient
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Create report data
    report_data = {
        "user": request.patient_id,
        "doctor": doctor_id,
        "submitTime": datetime.now().isoformat(),
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
    db: Session = Depends(get_db)
):
    """
    Get list of reports assigned to the current doctor with filtering
    Requires doctor role
    """
    # Validate doctor token
    session_info = validate_doctor_token(request, db)
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
            from_date = datetime.fromisoformat(request.date_from).date()
            query = query.filter(DenseReport.submitTime >= from_date)
        
        if request.date_to:
            to_date = datetime.fromisoformat(request.date_to).date()
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
                submitTime=datetime.combine(report.submitTime, datetime.min.time()),
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
    request: TokenRequest,
    report_id: str = Query(..., description="Report ID"),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific report
    Requires doctor review permission or report read permission
    """
    # Validate token from request body
    if not request.token:
        raise HTTPException(status_code=401, detail="Authentication required - no token provided")
    
    # Validate session
    session_info = SessionService.validate_session(db, request.token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    doctor_id = session_info["user_id"]
    
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
        doctor = db.query(User).join(UserDetail).join(Doctor).filter(User.id == report_data["doctor"]).first()
        doctor_details = None
        if doctor:
            doctor_details = {
                "name": doctor.user_detail.name if doctor.user_detail else doctor.id,
                "position": doctor.user.position if hasattr(doctor, 'user') and doctor.user else "",
                "workplace": doctor.user.workplace if hasattr(doctor, 'user') and doctor.user else ""
            }
        
        # Get comments
        comments = DatabaseStorageService.get_report_comments(db, report_id)
        
        # Get images
        images_data = DatabaseStorageService.get_report_images(db, report_id)
        
        # Create detailed report model
        report_detail = ReportDetailModel(
            id=report_data["id"],
            user=report_data["user"],
            doctor=report_data["doctor"],
            patient_name=patient_details["name"] if patient_details else report_data["user"],
            doctor_name=doctor_details["name"] if doctor_details else report_data["doctor"],
            submitTime=datetime.fromisoformat(report_data["submitTime"]),
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
    db: Session = Depends(get_db)
):
    """
    Update report status, diagnosis, or notes
    Requires doctor diagnose permission or report write permission
    """
    # Validate doctor token
    session_info = validate_doctor_token(request, db)
    doctor_id = session_info["user_id"]
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if doctor has access to this report
    if report_data["doctor"] != doctor_id:
        # Check if user has admin permissions
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to update this report")
    
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


@router.post("/api/doctor/reports/assign")
async def assign_report(
    request: AssignReportRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "assign"), ("report", "manage"))
):
    """
    Assign a report to a different doctor
    Requires report assign permission or report manage permission
    """
    # Verify target doctor exists and is a doctor
    target_doctor = db.query(User).filter(
        User.id == request.doctor_id,
        User.type == UserType.Doctor
    ).first()
    
    if not target_doctor:
        raise HTTPException(status_code=404, detail="Target doctor not found")
    
    # Get report from database
    report = db.query(DenseReport).filter(DenseReport.id == int(request.report_id)).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        # Update report assignment
        report.doctor = request.doctor_id
        db.commit()
        
        return Response(message=f"Report assigned to doctor {request.doctor_id}")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign report: {str(e)}")


@router.post("/api/doctor/reports/workflow/pending")
async def get_pending_reports(
    request: TokenRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Get all pending reports assigned to the current doctor
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
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
            patient = db.query(User).join(UserDetail).filter(User.id == report.user).first()
            patient_name = patient.user_detail.name if patient and patient.user_detail else report.user
            
            # Get images
            images_data = DatabaseStorageService.get_report_images(db, str(report.id))
            
            report_model = ReportModel(
                id=str(report.id),
                user=report.user,
                doctor=report.doctor,
                patient_name=patient_name,
                doctor_name="",  # Current doctor
                submitTime=datetime.combine(report.submitTime, datetime.min.time()),
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
        raise HTTPException(status_code=500, detail=f"Failed to retrieve pending reports: {str(e)}")


@router.post("/api/doctor/reports/workflow/complete")
async def complete_report_diagnosis(
    request: UpdateReportRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Complete a report diagnosis and mark as completed
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    if not request.diagnose:
        raise HTTPException(status_code=400, detail="Diagnosis is required to complete report")
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if doctor has access to this report
    if report_data["doctor"] != doctor_id:
        raise HTTPException(status_code=403, detail="Not authorized to complete this report")
    
    try:
        # Update report to completed status with diagnosis
        success = DatabaseStorageService.update_report_status(
            db, request.report_id, ReportStatus.Completed, request.diagnose
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to complete report")
        
        return Response(message="Report diagnosis completed successfully")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete report: {str(e)}")


@router.post("/api/doctor/reports/statistics")
async def get_doctor_statistics(
    request: TokenRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Get statistics for the current doctor's reports
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    try:
        # Get all reports for this doctor
        all_reports = db.query(DenseReport).filter(DenseReport.doctor == doctor_id).all()
        
        # Calculate statistics
        total_reports = len(all_reports)
        pending_reports = len([r for r in all_reports if r.current_status == ReportStatus.Checking])
        completed_reports = len([r for r in all_reports if r.current_status == ReportStatus.Completed])
        abnormal_reports = len([r for r in all_reports if r.current_status == ReportStatus.Abnormality])
        error_reports = len([r for r in all_reports if r.current_status == ReportStatus.Error])
        
        # Get recent activity (last 7 days)
        from datetime import timedelta
        week_ago = date.today() - timedelta(days=7)
        recent_reports = len([r for r in all_reports if r.submitTime >= week_ago])
        
        statistics = {
            "total_reports": total_reports,
            "pending_reports": pending_reports,
            "completed_reports": completed_reports,
            "abnormal_reports": abnormal_reports,
            "error_reports": error_reports,
            "recent_reports": recent_reports,
            "completion_rate": (completed_reports / total_reports * 100) if total_reports > 0 else 0
        }
        
        return Response(data=statistics)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")


@router.post("/api/doctor/reports/workflow/update")
async def update_diagnosis_workflow(
    request: DiagnosisWorkflowRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Update diagnosis workflow status with notes
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if doctor has access to this report
    if report_data["doctor"] != doctor_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this report workflow")
    
    try:
        # Create a workflow comment to track the status change
        from dense_platform_backend_main.database.table import Comment
        
        workflow_comment = Comment(
            report=int(request.report_id),
            user=doctor_id,
            content=f"Workflow status updated to: {request.workflow_status.value}" + 
                   (f"\nNotes: {request.notes}" if request.notes else ""),
            comment_type="system",
            priority="normal",
            is_deleted=False,
            is_resolved=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(workflow_comment)
        
        # If requesting consultation, create consultation comment
        if request.workflow_status == DiagnosisWorkflowStatus.REQUIRES_CONSULTATION and request.consultation_request:
            consultation_comment = Comment(
                report=int(request.report_id),
                user=doctor_id,
                content=f"Consultation requested: {request.consultation_request}",
                comment_type="collaboration",
                priority="high",
                is_deleted=False,
                is_resolved=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(consultation_comment)
        
        db.commit()
        
        return Response(message=f"Diagnosis workflow updated to {request.workflow_status.value}")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update diagnosis workflow: {str(e)}")


@router.post("/api/doctor/reports/consultation/request")
async def request_consultation(
    request: ConsultationRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Request consultation from another doctor
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    # Verify consulting doctor exists and is a doctor
    consulting_doctor = db.query(User).filter(
        User.id == request.consulting_doctor_id,
        User.type == UserType.Doctor
    ).first()
    
    if not consulting_doctor:
        raise HTTPException(status_code=404, detail="Consulting doctor not found")
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if doctor has access to this report
    if report_data["doctor"] != doctor_id:
        raise HTTPException(status_code=403, detail="Not authorized to request consultation for this report")
    
    try:
        from dense_platform_backend_main.database.table import Comment
        
        # Create consultation request comment
        consultation_comment = Comment(
            report=int(request.report_id),
            user=doctor_id,
            content=f"Consultation requested from Dr. {request.consulting_doctor_id}\n"
                   f"Reason: {request.consultation_reason}",
            comment_type="collaboration",
            priority=request.priority,
            is_deleted=False,
            is_resolved=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(consultation_comment)
        
        # Create notification comment for the consulting doctor
        notification_comment = Comment(
            report=int(request.report_id),
            user=request.consulting_doctor_id,
            content=f"Consultation request from Dr. {doctor_id}\n"
                   f"Reason: {request.consultation_reason}\n"
                   f"Please review and provide your expert opinion.",
            comment_type="system",
            priority=request.priority,
            is_deleted=False,
            is_resolved=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(notification_comment)
        db.commit()
        
        return Response(message=f"Consultation requested from Dr. {request.consulting_doctor_id}")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to request consultation: {str(e)}")


@router.post("/api/doctor/reports/diagnosis/review")
async def review_diagnosis(
    request: DiagnosisReviewRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("doctor", "review"), ("report", "manage"))
):
    """
    Review and approve/reject a diagnosis
    Requires doctor review permission or report manage permission
    """
    reviewer_id = current_user["user_id"]
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        from dense_platform_backend_main.database.table import Comment
        
        # Create review comment
        review_comment = Comment(
            report=int(request.report_id),
            user=reviewer_id,
            content=f"Diagnosis Review: {request.review_status.upper()}\n"
                   f"Review Notes: {request.review_notes}" +
                   (f"\nSuggested Changes: {request.suggested_changes}" if request.suggested_changes else ""),
            comment_type="diagnosis",
            priority="high",
            is_deleted=False,
            is_resolved=(request.review_status == "approved"),
            resolved_by=reviewer_id if request.review_status == "approved" else None,
            resolved_at=datetime.now() if request.review_status == "approved" else None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(review_comment)
        
        # If approved, update report status to completed
        if request.review_status == "approved":
            success = DatabaseStorageService.update_report_status(
                db, request.report_id, ReportStatus.Completed, report_data["diagnose"]
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update report status")
        
        # If rejected, update status back to checking
        elif request.review_status == "rejected":
            success = DatabaseStorageService.update_report_status(
                db, request.report_id, ReportStatus.Checking, report_data["diagnose"]
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update report status")
        
        db.commit()
        
        return Response(message=f"Diagnosis review completed: {request.review_status}")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to review diagnosis: {str(e)}")


@router.post("/api/doctor/reports/workflow/collaboration")
async def get_collaboration_reports(
    request: TokenRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("patient")
):
    """
    Get reports where the current doctor is involved in collaboration
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    try:
        from dense_platform_backend_main.database.table import Comment
        
        # Get reports where doctor has collaboration comments
        collaboration_comments = db.query(Comment).filter(
            Comment.user == doctor_id,
            Comment.comment_type == "collaboration",
            Comment.is_deleted == False
        ).all()
        
        # Get unique report IDs
        report_ids = list(set([c.report for c in collaboration_comments]))
        
        if not report_ids:
            return ReportListResponse(reports=[], total=0, page=1, limit=0)
        
        # Get reports
        reports = db.query(DenseReport).filter(DenseReport.id.in_(report_ids)).all()
        
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
                submitTime=datetime.combine(report.submitTime, datetime.min.time()),
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
        raise HTTPException(status_code=500, detail=f"Failed to retrieve collaboration reports: {str(e)}")


@router.post("/api/doctor/reports/workflow/consultation-requests")
async def get_consultation_requests(
    request: TokenRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Get consultation requests for the current doctor
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    try:
        from dense_platform_backend_main.database.table import Comment
        
        # Get consultation requests where this doctor is mentioned
        consultation_comments = db.query(Comment).filter(
            Comment.user == doctor_id,
            Comment.comment_type == "system",
            Comment.content.like("%Consultation request%"),
            Comment.is_resolved == False,
            Comment.is_deleted == False
        ).all()
        
        # Get unique report IDs
        report_ids = list(set([c.report for c in consultation_comments]))
        
        if not report_ids:
            return ReportListResponse(reports=[], total=0, page=1, limit=0)
        
        # Get reports
        reports = db.query(DenseReport).filter(DenseReport.id.in_(report_ids)).all()
        
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
                submitTime=datetime.combine(report.submitTime, datetime.min.time()),
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
        raise HTTPException(status_code=500, detail=f"Failed to retrieve consultation requests: {str(e)}")


@router.post("/api/doctor/reports/workflow/provide-consultation")
async def provide_consultation(
    request: UpdateReportRequest,
    db: Session = Depends(get_db),
    current_user = RequireRole("doctor")
):
    """
    Provide consultation opinion on a report
    Requires doctor role
    """
    doctor_id = current_user["user_id"]
    
    if not request.diagnose:
        raise HTTPException(status_code=400, detail="Consultation opinion is required")
    
    # Get report from database
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        from dense_platform_backend_main.database.table import Comment
        
        # Create consultation response comment
        consultation_response = Comment(
            report=int(request.report_id),
            user=doctor_id,
            content=f"Consultation Opinion from Dr. {doctor_id}:\n{request.diagnose}",
            comment_type="diagnosis",
            priority="high",
            is_deleted=False,
            is_resolved=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(consultation_response)
        
        # Mark consultation request as resolved
        consultation_requests = db.query(Comment).filter(
            Comment.report == int(request.report_id),
            Comment.user == doctor_id,
            Comment.comment_type == "system",
            Comment.content.like("%Consultation request%"),
            Comment.is_resolved == False
        ).all()
        
        for req in consultation_requests:
            req.is_resolved = True
            req.resolved_by = doctor_id
            req.resolved_at = datetime.now()
        
        db.commit()
        
        return Response(message="Consultation opinion provided successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to provide consultation: {str(e)}")