"""
Doctor Comment System API (Fixed Version)

This module provides comprehensive comment system with threading support
for medical reports and collaboration features.
Fixed to use token from Authorization header instead of request body.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from dense_platform_backend_main.database.table import Comment, DenseReport, User, UserDetail, UserType
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.services.rbac_middleware import RequireAnyPermission, RequireRole
from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.api.doctor.token_dependency import validate_doctor_token
from dense_platform_backend_main.utils.response import Response

router = APIRouter()


class CreateCommentRequest(BaseModel):
    """Request model for creating a new comment"""
    report_id: str = Field(..., description="Report ID to comment on")
    content: str = Field(..., min_length=1, max_length=4096, description="Comment content")
    parent_id: Optional[str] = Field(None, description="Parent comment ID for threading")
    comment_type: str = Field("general", description="Comment type: general, diagnosis, collaboration, system")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")
    mentions: List[str] = Field(default=[], description="List of user IDs to mention")


class UpdateCommentRequest(BaseModel):
    """Request model for updating a comment"""
    comment_id: str = Field(..., description="Comment ID to update")
    content: str = Field(..., min_length=1, max_length=4096, description="Updated comment content")


class DeleteCommentRequest(BaseModel):
    """Request model for deleting a comment"""
    comment_id: str = Field(..., description="Comment ID to delete")


class ResolveCommentRequest(BaseModel):
    """Request model for resolving a comment"""
    comment_id: str = Field(..., description="Comment ID to resolve")
    resolution_note: Optional[str] = Field(None, description="Optional resolution note")


class CommentFilterRequest(BaseModel):
    """Request model for filtering comments"""
    report_id: str = Field(..., description="Report ID to get comments for")
    comment_type: Optional[str] = Field(None, description="Filter by comment type")
    priority: Optional[str] = Field(None, description="Filter by priority")
    is_resolved: Optional[bool] = Field(None, description="Filter by resolution status")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    limit: int = Field(50, description="Maximum number of comments")
    offset: int = Field(0, description="Offset for pagination")


class GetCommentsRequest(BaseModel):
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


@router.post("/api/doctor/comments/create")
async def create_comment(
    request: CreateCommentRequest,
    db: Session = Depends(get_db),
    session_info: Dict[str, Any] = Depends(validate_doctor_token)
):
    """
    Create a new comment on a report
    Requires report comment permission, doctor review permission, or patient reports permission
    """
    user_id = session_info["user_id"]
    
    # Verify report exists and user has access
    report_data = DatabaseStorageService.load_report(db, request.