"""
Doctor Comment System API

This module provides comprehensive comment system with threading support
for medical reports and collaboration features.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from dense_platform_backend_main.database.table import Comment, DenseReport, User, UserDetail, UserType
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.services.rbac_middleware import RequireAnyPermission, RequireRole
from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response

router = APIRouter()

# Create security scheme for Bearer token
security = HTTPBearer(auto_error=False)


class CreateCommentRequest(TokenRequest):
    """Request model for creating a new comment"""
    report_id: str = Field(..., description="Report ID to comment on")
    content: str = Field(..., min_length=1, max_length=4096, description="Comment content")
    parent_id: Optional[str] = Field(None, description="Parent comment ID for threading")
    comment_type: str = Field("general", description="Comment type: general, diagnosis, collaboration, system")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")
    mentions: List[str] = Field(default=[], description="List of user IDs to mention")


class UpdateCommentRequest(TokenRequest):
    """Request model for updating a comment"""
    comment_id: str = Field(..., description="Comment ID to update")
    content: str = Field(..., min_length=1, max_length=4096, description="Updated comment content")


class DeleteCommentRequest(TokenRequest):
    """Request model for deleting a comment"""
    comment_id: str = Field(..., description="Comment ID to delete")


class ResolveCommentRequest(TokenRequest):
    """Request model for resolving a comment"""
    comment_id: str = Field(..., description="Comment ID to resolve")
    resolution_note: Optional[str] = Field(None, description="Optional resolution note")


class CommentFilterRequest(TokenRequest):
    """Request model for filtering comments"""
    report_id: str = Field(..., description="Report ID to get comments for")
    comment_type: Optional[str] = Field(None, description="Filter by comment type")
    priority: Optional[str] = Field(None, description="Filter by priority")
    is_resolved: Optional[bool] = Field(None, description="Filter by resolution status")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    limit: int = Field(50, description="Maximum number of comments")
    offset: int = Field(0, description="Offset for pagination")


class GetCommentsRequest(TokenRequest):
    """Request model for getting comments"""
    report_id: str = Field(..., description="Report ID to get comments for")
    include_deleted: bool = Field(False, description="Include deleted comments")
    limit: int = Field(50, description="Maximum number of comments")
    offset: int = Field(0, description="Offset for pagination")


class CommentModel(BaseModel):
    """Comment data model"""
    class Config:
        from_attributes = True
    
    id: str
    report_id: str
    user_id: str
    user_name: str
    user_type: str
    content: str
    parent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    replies: List['CommentModel'] = []
    reply_count: int = 0


class CommentResponse(Response):
    """Response model for single comment"""
    comment: CommentModel


class CommentsListResponse(Response):
    """Response model for comment lists"""
    comments: List[CommentModel]
    total: int
    page: int
    limit: int


class CommentStatsResponse(Response):
    """Response model for comment statistics"""
    total_comments: int
    user_comments: int
    recent_comments: int
    active_discussions: int


# Update the model to handle forward references
# CommentModel.model_rebuild()  # Not needed in Pydantic 1.x


@router.post("/api/doctor/comments/create")
async def create_comment(
    request: CreateCommentRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "comment"), ("doctor", "review"), ("patient", "reports"))
):
    """
    Create a new comment on a report
    Requires report comment permission, doctor review permission, or patient reports permission
    """
    user_id = current_user["user_id"]
    
    # Verify report exists and user has access
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if user has access to this report
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Patients can only comment on their own reports, doctors can comment on assigned reports
    if user.type == UserType.Patient and report_data["user"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to comment on this report")
    elif user.type == UserType.Doctor and report_data["doctor"] != user_id:
        # Check if user has admin permissions
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to comment on this report")
    
    # Verify parent comment exists if specified
    if request.parent_id:
        parent_comment = db.query(Comment).filter(
            Comment.id == int(request.parent_id),
            Comment.report == int(request.report_id)
        ).first()
        if not parent_comment:
            raise HTTPException(status_code=404, detail="Parent comment not found")
    
    try:
        # Create comment using proper database fields
        comment = Comment(
            report=int(request.report_id),
            user=user_id,
            content=request.content,
            parent_id=int(request.parent_id) if request.parent_id else None,
            comment_type=request.comment_type,
            priority=request.priority,
            is_deleted=False,
            is_resolved=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(comment)
        db.flush()  # Get the ID
        db.commit()
        
        # Get user details for response
        user_detail = db.query(UserDetail).filter(UserDetail.id == user_id).first()
        user_name = user_detail.name if user_detail else user_id
        user_type = "Doctor" if user.type == UserType.Doctor else "Patient"
        
        # Create response model
        comment_model = CommentModel(
            id=str(comment.id),
            report_id=request.report_id,
            user_id=user_id,
            user_name=user_name,
            user_type=user_type,
            content=request.content,  # Return original content without metadata
            parent_id=request.parent_id,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            is_deleted=False,
            replies=[],
            reply_count=0
        )
        
        return CommentResponse(comment=comment_model)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create comment: {str(e)}")


@router.post("/api/doctor/comments/list")
async def get_comments(
    request: GetCommentsRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "read"), ("doctor", "review"), ("patient", "reports"))
):
    """
    Get comments for a report with threading support
    Requires report read permission, doctor review permission, or patient reports permission
    """
    user_id = current_user["user_id"]
    
    # Verify report exists and user has access
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if user has access to this report
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Access control check
    if user.type == UserType.Patient and report_data["user"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view comments on this report")
    elif user.type == UserType.Doctor and report_data["doctor"] != user_id:
        # Check if user has admin permissions
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to view comments on this report")
    
    try:
        # Get comments from database
        query = db.query(Comment).filter(Comment.report == int(request.report_id))
        
        if not request.include_deleted:
            # Filter out deleted comments using the is_deleted flag
            query = query.filter(Comment.is_deleted == False)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        comments = query.order_by(desc(Comment.created_at)).offset(request.offset).limit(request.limit).all()
        
        # Build comment models with threading
        comment_models = []
        comment_dict = {}  # For building thread structure
        
        for comment in comments:
            # Get user details
            comment_user = db.query(User).filter(User.id == comment.user).first()
            user_detail = db.query(UserDetail).filter(UserDetail.id == comment.user).first()
            
            user_name = user_detail.name if user_detail else comment.user
            user_type = "Doctor" if comment_user and comment_user.type == UserType.Doctor else "Patient"
            
            # Use the actual parent_id field from database
            parent_id = str(comment.parent_id) if comment.parent_id else None
            
            comment_model = CommentModel(
                id=str(comment.id),
                report_id=request.report_id,
                user_id=comment.user,
                user_name=user_name,
                user_type=user_type,
                content=comment.content,
                parent_id=parent_id,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                replies=[],
                reply_count=0
            )
            
            comment_dict[str(comment.id)] = comment_model
            
            # If this is a top-level comment, add to main list
            if not parent_id:
                comment_models.append(comment_model)
        
        # Build thread structure
        for comment_id, comment_model in comment_dict.items():
            if comment_model.parent_id and comment_model.parent_id in comment_dict:
                parent = comment_dict[comment_model.parent_id]
                parent.replies.append(comment_model)
                parent.reply_count += 1
        
        # Sort replies by creation time
        for comment in comment_models:
            comment.replies.sort(key=lambda x: x.created_at)
        
        return CommentsListResponse(
            comments=comment_models,
            total=total,
            page=request.offset // request.limit + 1,
            limit=request.limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve comments: {str(e)}")


@router.post("/api/doctor/comments/update")
async def update_comment(
    request: UpdateCommentRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "comment"), ("doctor", "review"))
):
    """
    Update a comment (only by the original author or admin)
    Requires report comment permission or doctor review permission
    """
    user_id = current_user["user_id"]
    
    # Get comment from database
    comment = db.query(Comment).filter(Comment.id == int(request.comment_id)).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if user is the author or has admin permissions
    if comment.user != user_id:
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to update this comment")
    
    try:
        # Update comment content and timestamp
        comment.content = request.content
        comment.updated_at = datetime.now()
        
        db.commit()
        
        return Response(message="Comment updated successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update comment: {str(e)}")


@router.post("/api/doctor/comments/delete")
async def delete_comment(
    request: DeleteCommentRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "comment"), ("doctor", "review"))
):
    """
    Delete a comment (only by the original author or admin)
    Requires report comment permission or doctor review permission
    """
    user_id = current_user["user_id"]
    
    # Get comment from database
    comment = db.query(Comment).filter(Comment.id == int(request.comment_id)).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if user is the author or has admin permissions
    if comment.user != user_id:
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    
    try:
        # For now, we'll do hard delete. In production, consider soft delete
        db.delete(comment)
        db.commit()
        
        return Response(message="Comment deleted successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete comment: {str(e)}")


@router.post("/api/doctor/comments/statistics")
async def get_comment_statistics(
    request: TokenRequest,
    report_id: str = Query(..., description="Report ID"),
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "read"), ("doctor", "review"))
):
    """
    Get comment statistics for a report
    Requires report read permission or doctor review permission
    """
    user_id = current_user["user_id"]
    
    # Verify report exists and user has access
    report_data = DatabaseStorageService.load_report(db, report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        # Get all comments for this report
        all_comments = db.query(Comment).filter(Comment.report == int(report_id)).all()
        
        # Calculate statistics
        total_comments = len(all_comments)
        user_comments = len([c for c in all_comments if c.user == user_id])
        
        # Recent comments (last 24 hours)
        from datetime import timedelta
        day_ago = datetime.now() - timedelta(days=1)
        recent_comments = len([c for c in all_comments if c.created_at >= day_ago])
        
        # Active discussions (comments with replies)
        parent_comments = set()
        for comment in all_comments:
            if comment.parent_id:
                parent_comments.add(str(comment.parent_id))
        
        active_discussions = len(parent_comments)
        
        statistics = {
            "total_comments": total_comments,
            "user_comments": user_comments,
            "recent_comments": recent_comments,
            "active_discussions": active_discussions
        }
        
        return CommentStatsResponse(**statistics)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve comment statistics: {str(e)}")


@router.post("/api/doctor/comments/collaboration/mentions")
async def get_collaboration_mentions(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get comments where the current doctor is mentioned or needs attention
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
    from dense_platform_backend_main.api.auth.session import SessionService
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
        # Get all reports assigned to this doctor
        doctor_reports = db.query(DenseReport).filter(DenseReport.doctor == doctor_id).all()
        report_ids = [str(r.id) for r in doctor_reports]
        
        if not report_ids:
            return CommentsListResponse(comments=[], total=0, page=1, limit=0)
        
        # Get recent comments on these reports (excluding doctor's own comments)
        # Only select fields that exist in the database
        comments = db.query(Comment.id, Comment.report, Comment.user, Comment.content, 
                          Comment.created_at, Comment.updated_at, Comment.is_deleted).filter(
            Comment.report.in_([int(rid) for rid in report_ids]),
            Comment.user != doctor_id
        ).order_by(desc(Comment.created_at)).limit(20).all()
        
        # Build comment models
        comment_models = []
        for comment in comments:
            # Get user details
            comment_user = db.query(User).filter(User.id == comment.user).first()
            user_detail = db.query(UserDetail).filter(UserDetail.id == comment.user).first()
            
            user_name = user_detail.name if user_detail else comment.user
            user_type = "Doctor" if comment_user and comment_user.type == UserType.Doctor else "Patient"
            
            # parent_id field doesn't exist in current database schema
            parent_id = None
            
            comment_model = CommentModel(
                id=str(comment.id),
                report_id=str(comment.report),
                user_id=comment.user,
                user_name=user_name,
                user_type=user_type,
                content=comment.content,
                parent_id=parent_id,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                replies=[],
                reply_count=0
            )
            comment_models.append(comment_model)
        
        return CommentsListResponse(
            comments=comment_models,
            total=len(comment_models),
            page=1,
            limit=len(comment_models)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve collaboration mentions: {str(e)}")


@router.post("/api/doctor/comments/resolve")
async def resolve_comment(
    request: ResolveCommentRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "comment"), ("doctor", "review"))
):
    """
    Resolve a comment (mark as resolved)
    Requires report comment permission or doctor review permission
    """
    user_id = current_user["user_id"]
    
    # Get comment from database
    comment = db.query(Comment).filter(Comment.id == int(request.comment_id)).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if user has permission to resolve comments
    user = db.query(User).filter(User.id == user_id).first()
    if user.type != UserType.Doctor:
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to resolve comments")
    
    try:
        # Mark comment as resolved
        comment.is_resolved = True
        comment.resolved_by = user_id
        comment.resolved_at = datetime.now()
        comment.updated_at = datetime.now()
        
        # Add resolution note as a system comment if provided
        if request.resolution_note:
            resolution_comment = Comment(
                report=comment.report,
                user=user_id,
                content=f"Resolution: {request.resolution_note}",
                parent_id=comment.id,
                comment_type="system",
                priority="normal",
                is_deleted=False,
                is_resolved=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(resolution_comment)
        
        db.commit()
        
        return Response(message="Comment resolved successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to resolve comment: {str(e)}")


@router.post("/api/doctor/comments/filter")
async def filter_comments(
    request: CommentFilterRequest,
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("report", "read"), ("doctor", "review"), ("patient", "reports"))
):
    """
    Get filtered comments for a report with advanced filtering options
    Requires report read permission, doctor review permission, or patient reports permission
    """
    user_id = current_user["user_id"]
    
    # Verify report exists and user has access
    report_data = DatabaseStorageService.load_report(db, request.report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if user has access to this report
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Access control check
    if user.type == UserType.Patient and report_data["user"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view comments on this report")
    elif user.type == UserType.Doctor and report_data["doctor"] != user_id:
        # Check if user has admin permissions
        if not any(perm["resource"] == "report" and perm["action"] == "manage" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to view comments on this report")
    
    try:
        # Build query with filters
        query = db.query(Comment).filter(
            Comment.report == int(request.report_id),
            Comment.is_deleted == False
        )
        
        # Apply filters
        if request.comment_type:
            query = query.filter(Comment.comment_type == request.comment_type)
        
        if request.priority:
            query = query.filter(Comment.priority == request.priority)
        
        if request.is_resolved is not None:
            query = query.filter(Comment.is_resolved == request.is_resolved)
        
        if request.user_id:
            query = query.filter(Comment.user == request.user_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        comments = query.order_by(desc(Comment.created_at)).offset(request.offset).limit(request.limit).all()
        
        # Build comment models
        comment_models = []
        for comment in comments:
            # Get user details
            comment_user = db.query(User).filter(User.id == comment.user).first()
            user_detail = db.query(UserDetail).filter(UserDetail.id == comment.user).first()
            
            user_name = user_detail.name if user_detail else comment.user
            user_type = "Doctor" if comment_user and comment_user.type == UserType.Doctor else "Patient"
            
            comment_model = CommentModel(
                id=str(comment.id),
                report_id=request.report_id,
                user_id=comment.user,
                user_name=user_name,
                user_type=user_type,
                content=comment.content,
                parent_id=str(comment.parent_id) if comment.parent_id else None,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                replies=[],
                reply_count=0
            )
            comment_models.append(comment_model)
        
        return CommentsListResponse(
            comments=comment_models,
            total=total,
            page=request.offset // request.limit + 1,
            limit=request.limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to filter comments: {str(e)}")


@router.post("/api/doctor/comments/collaboration/urgent")
async def get_urgent_comments(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get urgent comments that need immediate attention
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
    from dense_platform_backend_main.api.auth.session import SessionService
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
        # Get all reports assigned to this doctor
        doctor_reports = db.query(DenseReport).filter(DenseReport.doctor == doctor_id).all()
        report_ids = [r.id for r in doctor_reports]
        
        if not report_ids:
            return CommentsListResponse(comments=[], total=0, page=1, limit=0)
        
        # Get urgent unresolved comments on these reports
        comments = db.query(Comment).filter(
            Comment.report.in_(report_ids),
            Comment.priority == "urgent",
            Comment.is_resolved == False,
            Comment.is_deleted == False
        ).order_by(desc(Comment.created_at)).all()
        
        # Build comment models
        comment_models = []
        for comment in comments:
            # Get user details
            comment_user = db.query(User).filter(User.id == comment.user).first()
            user_detail = db.query(UserDetail).filter(UserDetail.id == comment.user).first()
            
            user_name = user_detail.name if user_detail else comment.user
            user_type = "Doctor" if comment_user and comment_user.type == UserType.Doctor else "Patient"
            
            comment_model = CommentModel(
                id=str(comment.id),
                report_id=str(comment.report),
                user_id=comment.user,
                user_name=user_name,
                user_type=user_type,
                content=comment.content,
                parent_id=str(comment.parent_id) if comment.parent_id else None,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=False,
                replies=[],
                reply_count=0
            )
            comment_models.append(comment_model)
        
        return CommentsListResponse(
            comments=comment_models,
            total=len(comment_models),
            page=1,
            limit=len(comment_models)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve urgent comments: {str(e)}")


@router.post("/api/doctor/comments/collaboration/team")
async def get_team_discussion(
    request: TokenRequest,
    report_id: str = Query(..., description="Report ID"),
    db: Session = Depends(get_db),
    current_user = RequireAnyPermission(("doctor", "review"), ("report", "read"))
):
    """
    Get team discussion comments for collaborative diagnosis
    Requires doctor review permission or report read permission
    """
    user_id = current_user["user_id"]
    
    # Verify report exists and user has access
    report_data = DatabaseStorageService.load_report(db, report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        # Get collaboration comments for this report
        comments = db.query(Comment).filter(
            Comment.report == int(report_id),
            Comment.comment_type == "collaboration",
            Comment.is_deleted == False
        ).order_by(Comment.created_at).all()
        
        # Build threaded comment structure
        comment_dict = {}
        root_comments = []
        
        for comment in comments:
            # Get user details
            comment_user = db.query(User).filter(User.id == comment.user).first()
            user_detail = db.query(UserDetail).filter(UserDetail.id == comment.user).first()
            
            user_name = user_detail.name if user_detail else comment.user
            user_type = "Doctor" if comment_user and comment_user.type == UserType.Doctor else "Patient"
            
            comment_model = CommentModel(
                id=str(comment.id),
                report_id=report_id,
                user_id=comment.user,
                user_name=user_name,
                user_type=user_type,
                content=comment.content,
                parent_id=str(comment.parent_id) if comment.parent_id else None,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                replies=[],
                reply_count=0
            )
            
            comment_dict[str(comment.id)] = comment_model
            
            if not comment.parent_id:
                root_comments.append(comment_model)
        
        # Build thread structure
        for comment_id, comment_model in comment_dict.items():
            if comment_model.parent_id and comment_model.parent_id in comment_dict:
                parent = comment_dict[comment_model.parent_id]
                parent.replies.append(comment_model)
                parent.reply_count += 1
        
        # Sort replies by creation time
        for comment in root_comments:
            comment.replies.sort(key=lambda x: x.created_at)
        
        return CommentsListResponse(
            comments=root_comments,
            total=len(comments),
            page=1,
            limit=len(comments)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve team discussion: {str(e)}")