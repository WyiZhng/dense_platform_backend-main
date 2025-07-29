"""
Audit Log Management API

This module provides API endpoints for viewing and managing audit logs.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from pydantic import BaseModel, Field

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.database.table import AuditLog, User
from dense_platform_backend_main.services.rbac_middleware import RequirePermission
from dense_platform_backend_main.utils.response import success_response, error_response

router = APIRouter(prefix="/api/admin/audit", tags=["Admin Audit"])


# Pydantic models for request/response
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None


@router.get("/events")
async def get_audit_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="限制数量（兼容前端）"),
    user_id: Optional[str] = Query(None, description="用户ID筛选"),
    action: Optional[str] = Query(None, description="操作类型筛选"),
    event_type: Optional[str] = Query(None, description="事件类型筛选（兼容前端）"),
    resource_type: Optional[str] = Query(None, description="资源类型筛选"),
    success: Optional[bool] = Query(None, description="是否成功筛选"),
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    hours: Optional[int] = Query(None, ge=1, description="最近几小时（兼容前端）"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    获取审计日志列表
    
    Requires: admin:audit permission
    """
    try:
        # 构建查询
        query = db.query(AuditLog).outerjoin(User, AuditLog.user_id == User.id)
        
        # 应用筛选条件
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if action:
            query = query.filter(AuditLog.action.ilike(f"%{action}%"))
        
        # 兼容前端的 event_type 参数
        if event_type:
            query = query.filter(AuditLog.action.ilike(f"%{event_type}%"))
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if success is not None:
            query = query.filter(AuditLog.success == success)
        
        # 时间范围筛选 - 支持前端的 hours 参数
        if hours:
            hours_ago = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(AuditLog.timestamp >= hours_ago)
        
        # 日期范围筛选
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(AuditLog.timestamp >= date_from_obj)
            except ValueError:
                return error_response(message="开始日期格式错误，请使用 YYYY-MM-DD 格式")
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(AuditLog.timestamp < date_to_obj)
            except ValueError:
                return error_response(message="结束日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 搜索功能
        if search:
            search_filter = or_(
                AuditLog.action.ilike(f"%{search}%"),
                AuditLog.resource_type.ilike(f"%{search}%"),
                AuditLog.resource_id.ilike(f"%{search}%"),
                AuditLog.old_values.ilike(f"%{search}%"),
                AuditLog.new_values.ilike(f"%{search}%"),
                AuditLog.error_message.ilike(f"%{search}%"),
                User.id.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        # 获取总数
        total = query.count()
        
        # 处理分页和限制参数
        if limit:
            # 如果前端提供了 limit 参数，使用它而不是分页
            logs = query.order_by(desc(AuditLog.timestamp)).limit(limit).all()
            page_size = limit
            page = 1
            offset = 0
        else:
            # 使用传统分页
            offset = (page - 1) * page_size
            logs = query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(page_size).all()
        
        # 构建响应数据
        log_responses = []
        for log in logs:
            log_responses.append({
                "id": log.id,
                "user_id": log.user_id,
                "user_name": log.user.id if log.user else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "success": log.success,
                "error_message": log.error_message
            })
        
        total_pages = (total + page_size - 1) // page_size
        
        response_data = {
            "events": log_responses,  # 前端期望的字段名
            "total_count": total,     # 前端期望的字段名
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "filters": {              # 前端期望的过滤器信息
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "success": success,
                "date_from": date_from,
                "date_to": date_to,
                "search": search
            }
        }
        
        return success_response(
            data=response_data,
            message="获取审计事件成功"
        )
        
    except Exception as e:
        return error_response(message=f"获取审计日志失败: {str(e)}")


@router.get("/events/{log_id}")
async def get_audit_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    获取单个审计日志详情
    
    Requires: admin:audit permission
    """
    try:
        log = db.query(AuditLog).outerjoin(User, AuditLog.user_id == User.id).filter(
            AuditLog.id == log_id
        ).first()
        
        if not log:
            return error_response(message="审计日志不存在", code=404)
        
        log_response = {
            "id": log.id,
            "user_id": log.user_id,
            "user_name": log.user.id if log.user else None,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "success": log.success,
            "error_message": log.error_message
        }
        
        return success_response(
            data=log_response,
            message="成功获取审计日志详情"
        )
        
    except Exception as e:
        return error_response(message=f"获取审计日志详情失败: {str(e)}")


@router.get("/stats/summary")
async def get_audit_stats_summary(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    获取审计日志统计摘要
    
    Requires: admin:audit permission
    """
    try:
        # 计算时间范围
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 基础统计
        total_logs = db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date
        ).count()
        
        successful_logs = db.query(AuditLog).filter(
            and_(
                AuditLog.timestamp >= start_date,
                AuditLog.success == True
            )
        ).count()
        
        failed_logs = db.query(AuditLog).filter(
            and_(
                AuditLog.timestamp >= start_date,
                AuditLog.success == False
            )
        ).count()
        
        # 按操作类型统计
        action_stats = db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= start_date
        ).group_by(AuditLog.action).order_by(desc('count')).limit(10).all()
        
        # 按资源类型统计
        resource_stats = db.query(
            AuditLog.resource_type,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= start_date
        ).group_by(AuditLog.resource_type).order_by(desc('count')).limit(10).all()
        
        # 按用户统计
        user_stats = db.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label('count')
        ).filter(
            and_(
                AuditLog.timestamp >= start_date,
                AuditLog.user_id.isnot(None)
            )
        ).group_by(AuditLog.user_id).order_by(desc('count')).limit(10).all()
        
        # 按日期统计（最近7天）
        daily_stats = []
        for i in range(7):
            day_start = (end_date - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_count = db.query(AuditLog).filter(
                and_(
                    AuditLog.timestamp >= day_start,
                    AuditLog.timestamp < day_end
                )
            ).count()
            
            daily_stats.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "count": day_count
            })
        
        daily_stats.reverse()  # 按时间正序排列
        
        stats_data = {
            "period_days": days,
            "total_logs": total_logs,
            "successful_logs": successful_logs,
            "failed_logs": failed_logs,
            "success_rate": round((successful_logs / total_logs * 100) if total_logs > 0 else 0, 2),
            "top_actions": [{"action": action, "count": count} for action, count in action_stats],
            "top_resources": [{"resource_type": resource, "count": count} for resource, count in resource_stats],
            "top_users": [{"user_id": user_id, "count": count} for user_id, count in user_stats],
            "daily_stats": daily_stats
        }
        
        return success_response(
            data=stats_data,
            message=f"成功获取最近 {days} 天的审计统计"
        )
        
    except Exception as e:
        return error_response(message=f"获取审计统计失败: {str(e)}")


@router.get("/actions")
async def get_audit_actions(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    获取所有可用的审计操作类型
    
    Requires: admin:audit permission
    """
    try:
        actions = db.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
        action_list = [action[0] for action in actions if action[0]]
        
        return success_response(
            data={"actions": action_list},
            message=f"成功获取 {len(action_list)} 个操作类型"
        )
        
    except Exception as e:
        return error_response(message=f"获取操作类型失败: {str(e)}")


@router.get("/resources")
async def get_audit_resources(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    获取所有可用的审计资源类型
    
    Requires: admin:audit permission
    """
    try:
        resources = db.query(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type).all()
        resource_list = [resource[0] for resource in resources if resource[0]]
        
        return success_response(
            data={"resource_types": resource_list},
            message=f"成功获取 {len(resource_list)} 个资源类型"
        )
        
    except Exception as e:
        return error_response(message=f"获取资源类型失败: {str(e)}")


@router.delete("/events/cleanup")
async def cleanup_old_audit_logs(
    days: int = Query(90, ge=30, le=365, description="保留天数"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    清理旧的审计日志
    
    Requires: admin:system permission
    """
    try:
        # 计算清理日期
        cleanup_date = datetime.utcnow() - timedelta(days=days)
        
        # 统计要删除的记录数
        count_to_delete = db.query(AuditLog).filter(
            AuditLog.timestamp < cleanup_date
        ).count()
        
        if count_to_delete == 0:
            return success_response(
                data={"deleted_count": 0},
                message=f"没有超过 {days} 天的审计日志需要清理"
            )
        
        # 执行删除
        deleted_count = db.query(AuditLog).filter(
            AuditLog.timestamp < cleanup_date
        ).delete()
        
        db.commit()
        
        return success_response(
            data={"deleted_count": deleted_count},
            message=f"成功清理 {deleted_count} 条超过 {days} 天的审计日志"
        )
        
    except Exception as e:
        db.rollback()
        return error_response(message=f"清理审计日志失败: {str(e)}")