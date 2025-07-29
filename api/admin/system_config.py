"""
Admin System Configuration API

This module provides API endpoints for system configuration management,
including application settings, feature toggles, and system parameters.
"""

from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
import json

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.services.rbac_middleware import RequirePermission
from dense_platform_backend_main.utils.response import success_response, error_response
from dense_platform_backend_main.database.table import AuditLog

router = APIRouter(prefix="/api/admin/config", tags=["Admin System Configuration"])


# Pydantic models for configuration
class ConfigurationItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=100, description="Configuration key")
    value: Union[str, int, float, bool, dict, list] = Field(..., description="Configuration value")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    category: Optional[str] = Field(None, max_length=50, description="Configuration category")
    is_sensitive: bool = Field(False, description="Whether this is sensitive configuration")


class UpdateConfigRequest(BaseModel):
    value: Union[str, int, float, bool, dict, list] = Field(..., description="New configuration value")
    description: Optional[str] = Field(None, max_length=500, description="Updated description")


# In-memory configuration store (in production, this would be in database or external config service)
SYSTEM_CONFIG = {
    # Authentication settings
    "auth.session_timeout_hours": {
        "value": 24,
        "description": "Session timeout in hours",
        "category": "authentication",
        "is_sensitive": False
    },
    "auth.max_login_attempts": {
        "value": 5,
        "description": "Maximum login attempts before lockout",
        "category": "authentication",
        "is_sensitive": False
    },
    "auth.lockout_duration_minutes": {
        "value": 30,
        "description": "Account lockout duration in minutes",
        "category": "authentication",
        "is_sensitive": False
    },
    
    # Report processing settings
    "reports.auto_assign_doctors": {
        "value": True,
        "description": "Automatically assign reports to available doctors",
        "category": "reports",
        "is_sensitive": False
    },
    "reports.max_processing_days": {
        "value": 7,
        "description": "Maximum days for report processing before escalation",
        "category": "reports",
        "is_sensitive": False
    },
    "reports.enable_ai_preprocessing": {
        "value": True,
        "description": "Enable AI preprocessing for medical images",
        "category": "reports",
        "is_sensitive": False
    },
    
    # System settings
    "system.maintenance_mode": {
        "value": False,
        "description": "Enable maintenance mode",
        "category": "system",
        "is_sensitive": False
    },
    "system.max_file_upload_mb": {
        "value": 50,
        "description": "Maximum file upload size in MB",
        "category": "system",
        "is_sensitive": False
    },
    "system.enable_audit_logging": {
        "value": True,
        "description": "Enable detailed audit logging",
        "category": "system",
        "is_sensitive": False
    },
    
    # Email settings
    "email.smtp_server": {
        "value": "smtp.example.com",
        "description": "SMTP server for email notifications",
        "category": "email",
        "is_sensitive": False
    },
    "email.smtp_port": {
        "value": 587,
        "description": "SMTP server port",
        "category": "email",
        "is_sensitive": False
    },
    "email.smtp_username": {
        "value": "noreply@example.com",
        "description": "SMTP username",
        "category": "email",
        "is_sensitive": True
    },
    "email.enable_notifications": {
        "value": True,
        "description": "Enable email notifications",
        "category": "email",
        "is_sensitive": False
    },
    
    # Feature flags
    "features.enable_patient_portal": {
        "value": True,
        "description": "Enable patient portal features",
        "category": "features",
        "is_sensitive": False
    },
    "features.enable_telemedicine": {
        "value": False,
        "description": "Enable telemedicine features",
        "category": "features",
        "is_sensitive": False
    },
    "features.enable_mobile_app": {
        "value": True,
        "description": "Enable mobile app support",
        "category": "features",
        "is_sensitive": False
    }
}


@router.get("/")
async def get_all_configurations(
    category: Optional[str] = Query(None, description="Filter by category"),
    include_sensitive: bool = Query(False, description="Include sensitive configurations"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get all system configurations
    
    Requires: admin:system permission
    """
    try:
        configurations = {}
        
        for key, config in SYSTEM_CONFIG.items():
            # Filter by category if specified
            if category and config.get("category") != category:
                continue
            
            # Skip sensitive configs unless explicitly requested
            if config.get("is_sensitive", False) and not include_sensitive:
                continue
            
            configurations[key] = {
                "value": config["value"],
                "description": config.get("description"),
                "category": config.get("category"),
                "is_sensitive": config.get("is_sensitive", False)
            }
        
        return success_response(
            data={"configurations": configurations},
            message="Configurations retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve configurations: {str(e)}")


@router.get("/categories")
async def get_configuration_categories(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get all configuration categories
    
    Requires: admin:system permission
    """
    try:
        categories = set()
        for config in SYSTEM_CONFIG.values():
            if config.get("category"):
                categories.add(config["category"])
        
        return success_response(
            data={"categories": sorted(list(categories))},
            message="Configuration categories retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve categories: {str(e)}")


@router.get("/{config_key}")
async def get_configuration(
    config_key: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Get a specific configuration
    
    Requires: admin:system permission
    """
    try:
        if config_key not in SYSTEM_CONFIG:
            return error_response(message="Configuration not found")
        
        config = SYSTEM_CONFIG[config_key]
        
        return success_response(
            data={
                "key": config_key,
                "value": config["value"],
                "description": config.get("description"),
                "category": config.get("category"),
                "is_sensitive": config.get("is_sensitive", False)
            },
            message="Configuration retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve configuration: {str(e)}")


@router.put("/{config_key}")
async def update_configuration(
    config_key: str,
    request: UpdateConfigRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Update a system configuration
    
    Requires: admin:system permission
    """
    try:
        if config_key not in SYSTEM_CONFIG:
            return error_response(message="Configuration not found")
        
        old_config = SYSTEM_CONFIG[config_key].copy()
        old_value = old_config["value"]
        
        # Update configuration
        SYSTEM_CONFIG[config_key]["value"] = request.value
        if request.description is not None:
            SYSTEM_CONFIG[config_key]["description"] = request.description
        
        # Create audit log
        audit_data = {
            "config_key": config_key,
            "old_value": old_value if not old_config.get("is_sensitive") else "[SENSITIVE]",
            "new_value": request.value if not old_config.get("is_sensitive") else "[SENSITIVE]"
        }
        
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="update_system_config",
            resource_type="system_config",
            resource_id=config_key,
            old_values=json.dumps({"value": old_value} if not old_config.get("is_sensitive") else {"value": "[SENSITIVE]"}),
            new_values=json.dumps({"value": request.value} if not old_config.get("is_sensitive") else {"value": "[SENSITIVE]"}),
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        return success_response(
            data={
                "key": config_key,
                "old_value": old_value if not old_config.get("is_sensitive") else "[SENSITIVE]",
                "new_value": request.value if not old_config.get("is_sensitive") else "[SENSITIVE]"
            },
            message="Configuration updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="update_system_config",
            resource_type="system_config",
            resource_id=config_key,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to update configuration: {str(e)}")


@router.post("/")
async def create_configuration(
    request: ConfigurationItem,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Create a new system configuration
    
    Requires: admin:system permission
    """
    try:
        if request.key in SYSTEM_CONFIG:
            return error_response(message="Configuration already exists")
        
        # Create new configuration
        SYSTEM_CONFIG[request.key] = {
            "value": request.value,
            "description": request.description,
            "category": request.category,
            "is_sensitive": request.is_sensitive
        }
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="create_system_config",
            resource_type="system_config",
            resource_id=request.key,
            new_values=json.dumps({
                "value": request.value if not request.is_sensitive else "[SENSITIVE]",
                "description": request.description,
                "category": request.category
            }),
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        return success_response(
            data={"key": request.key},
            message="Configuration created successfully"
        )
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="create_system_config",
            resource_type="system_config",
            resource_id=request.key,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to create configuration: {str(e)}")


@router.delete("/{config_key}")
async def delete_configuration(
    config_key: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Delete a system configuration
    
    Requires: admin:system permission
    """
    try:
        if config_key not in SYSTEM_CONFIG:
            return error_response(message="Configuration not found")
        
        old_config = SYSTEM_CONFIG[config_key].copy()
        
        # Delete configuration
        del SYSTEM_CONFIG[config_key]
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="delete_system_config",
            resource_type="system_config",
            resource_id=config_key,
            old_values=json.dumps({
                "value": old_config["value"] if not old_config.get("is_sensitive") else "[SENSITIVE]",
                "description": old_config.get("description"),
                "category": old_config.get("category")
            }),
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        return success_response(message="Configuration deleted successfully")
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="delete_system_config",
            resource_type="system_config",
            resource_id=config_key,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to delete configuration: {str(e)}")


@router.post("/reset-defaults")
async def reset_to_defaults(
    category: Optional[str] = Query(None, description="Reset only specific category"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Reset configurations to default values
    
    Requires: admin:system permission
    """
    try:
        # Default configurations (this would typically come from a config file)
        default_configs = {
            "auth.session_timeout_hours": 24,
            "auth.max_login_attempts": 5,
            "auth.lockout_duration_minutes": 30,
            "reports.auto_assign_doctors": True,
            "reports.max_processing_days": 7,
            "reports.enable_ai_preprocessing": True,
            "system.maintenance_mode": False,
            "system.max_file_upload_mb": 50,
            "system.enable_audit_logging": True,
            "email.enable_notifications": True,
            "features.enable_patient_portal": True,
            "features.enable_telemedicine": False,
            "features.enable_mobile_app": True
        }
        
        reset_count = 0
        reset_keys = []
        
        for key, default_value in default_configs.items():
            if key in SYSTEM_CONFIG:
                # Filter by category if specified
                if category and SYSTEM_CONFIG[key].get("category") != category:
                    continue
                
                old_value = SYSTEM_CONFIG[key]["value"]
                SYSTEM_CONFIG[key]["value"] = default_value
                reset_count += 1
                reset_keys.append(key)
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="reset_system_config_defaults",
            resource_type="system_config",
            resource_id=category or "all",
            new_values=json.dumps({
                "reset_count": reset_count,
                "reset_keys": reset_keys,
                "category": category
            }),
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        return success_response(
            data={
                "reset_count": reset_count,
                "reset_keys": reset_keys
            },
            message=f"Successfully reset {reset_count} configurations to defaults"
        )
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="reset_system_config_defaults",
            resource_type="system_config",
            resource_id=category or "all",
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to reset configurations: {str(e)}")


@router.get("/export/backup")
async def export_configuration_backup(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "system")
):
    """
    Export system configuration as backup
    
    Requires: admin:system permission
    """
    try:
        # Create backup of all configurations (excluding sensitive values)
        backup_data = {}
        
        for key, config in SYSTEM_CONFIG.items():
            backup_data[key] = {
                "value": config["value"] if not config.get("is_sensitive") else "[SENSITIVE_EXCLUDED]",
                "description": config.get("description"),
                "category": config.get("category"),
                "is_sensitive": config.get("is_sensitive", False)
            }
        
        backup_info = {
            "export_timestamp": datetime.now().isoformat(),
            "exported_by": current_user["user_id"],
            "total_configurations": len(backup_data),
            "configurations": backup_data
        }
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="export_system_config_backup",
            resource_type="system_config",
            resource_id="backup",
            new_values=json.dumps({
                "total_configurations": len(backup_data),
                "export_timestamp": backup_info["export_timestamp"]
            }),
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        return success_response(
            data=backup_info,
            message="Configuration backup exported successfully"
        )
        
    except Exception as e:
        db.rollback()
        return error_response(message=f"Failed to export configuration backup: {str(e)}")


def get_config_value(key: str, default=None):
    """
    Utility function to get configuration value
    
    Args:
        key: Configuration key
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    if key in SYSTEM_CONFIG:
        return SYSTEM_CONFIG[key]["value"]
    return default


def is_maintenance_mode() -> bool:
    """Check if system is in maintenance mode"""
    return get_config_value("system.maintenance_mode", False)


def get_session_timeout_hours() -> int:
    """Get session timeout in hours"""
    return get_config_value("auth.session_timeout_hours", 24)


def get_max_file_upload_mb() -> int:
    """Get maximum file upload size in MB"""
    return get_config_value("system.max_file_upload_mb", 50)