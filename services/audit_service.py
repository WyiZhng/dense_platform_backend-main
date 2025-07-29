"""
Audit Logging and Monitoring Service

This module provides comprehensive audit logging and security monitoring features including:
- Audit logging for sensitive operations
- Security monitoring and alerting
- User activity tracking
- System health monitoring
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from collections import defaultdict, deque
from threading import Lock
from dataclasses import dataclass, asdict
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Audit logging configuration
AUDIT_LOG_DIR = Path("logs/audit")
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# File handler for audit logs
audit_file_handler = logging.FileHandler(AUDIT_LOG_DIR / "audit.log")
audit_file_handler.setLevel(logging.INFO)

# JSON formatter for structured logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'audit_data'):
            # Convert datetime objects to ISO format strings
            audit_data = self._serialize_datetime_objects(record.audit_data)
            log_entry.update(audit_data)
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)
    
    def _serialize_datetime_objects(self, obj):
        """Recursively convert datetime objects to ISO format strings"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._serialize_datetime_objects(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime_objects(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Handle enum objects and other custom objects
            if hasattr(obj, 'value'):
                return obj.value
            return str(obj)
        else:
            return obj

audit_file_handler.setFormatter(JSONFormatter())
audit_logger.addHandler(audit_file_handler)

# Security monitoring logger
security_logger = logging.getLogger("security_monitor")
security_logger.setLevel(logging.WARNING)

security_file_handler = logging.FileHandler(AUDIT_LOG_DIR / "security.log")
security_file_handler.setLevel(logging.WARNING)
security_file_handler.setFormatter(JSONFormatter())
security_logger.addHandler(security_file_handler)


class AuditEventType(Enum):
    """Types of audit events"""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"
    ROLE_CHANGE = "role_change"
    
    # Data events
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
    
    # Security events
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALWARE_DETECTED = "malware_detected"
    
    # Admin events
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    ADMIN_ACTION = "admin_action"


class SeverityLevel(Enum):
    """Severity levels for audit events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure"""
    event_type: AuditEventType
    severity: SeverityLevel
    user_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class SecurityAlert:
    """Security alert data structure"""
    def __init__(
        self,
        alert_type: str,
        severity: SeverityLevel,
        message: str,
        details: Dict[str, Any],
        timestamp: datetime = None
    ):
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.details = details
        self.timestamp = timestamp or datetime.now()
        self.alert_id = f"{alert_type}_{int(time.time())}"


class ActivityTracker:
    """Track user activity patterns"""
    
    def __init__(self):
        self._user_activities = defaultdict(lambda: deque(maxlen=100))
        self._lock = Lock()
    
    def record_activity(self, user_id: str, activity_type: str, details: Dict[str, Any] = None):
        """Record user activity"""
        with self._lock:
            activity = {
                'timestamp': datetime.now(),
                'activity_type': activity_type,
                'details': details or {}
            }
            self._user_activities[user_id].append(activity)
    
    def get_user_activity(self, user_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get user activity for the last N hours"""
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=hours)
            activities = self._user_activities.get(user_id, deque())
            
            return [
                activity for activity in activities
                if activity['timestamp'] > cutoff
            ]
    
    def get_activity_summary(self, user_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get activity summary for a user"""
        activities = self.get_user_activity(user_id, hours)
        
        activity_counts = defaultdict(int)
        for activity in activities:
            activity_counts[activity['activity_type']] += 1
        
        return {
            'user_id': user_id,
            'period_hours': hours,
            'total_activities': len(activities),
            'activity_breakdown': dict(activity_counts),
            'first_activity': activities[0]['timestamp'] if activities else None,
            'last_activity': activities[-1]['timestamp'] if activities else None
        }


class SecurityMonitor:
    """Monitor for security threats and suspicious activities"""
    
    def __init__(self):
        self._failed_logins = defaultdict(list)
        self._suspicious_ips = defaultdict(int)
        self._alerts = deque(maxlen=1000)
        self._lock = Lock()
        
        # Thresholds for security monitoring
        self.FAILED_LOGIN_THRESHOLD = 5
        self.FAILED_LOGIN_WINDOW = 300  # 5 minutes
        self.SUSPICIOUS_IP_THRESHOLD = 10
        self.RATE_LIMIT_THRESHOLD = 100
    
    def record_failed_login(self, user_id: str, ip_address: str):
        """Record failed login attempt"""
        with self._lock:
            now = datetime.now()
            self._failed_logins[user_id].append({
                'timestamp': now,
                'ip_address': ip_address
            })
            
            # Clean old entries
            cutoff = now - timedelta(seconds=self.FAILED_LOGIN_WINDOW)
            self._failed_logins[user_id] = [
                attempt for attempt in self._failed_logins[user_id]
                if attempt['timestamp'] > cutoff
            ]
            
            # Check for suspicious activity
            if len(self._failed_logins[user_id]) >= self.FAILED_LOGIN_THRESHOLD:
                self._create_alert(
                    "multiple_failed_logins",
                    SeverityLevel.HIGH,
                    f"Multiple failed login attempts for user {user_id}",
                    {
                        'user_id': user_id,
                        'ip_address': ip_address,
                        'attempt_count': len(self._failed_logins[user_id]),
                        'time_window': self.FAILED_LOGIN_WINDOW
                    }
                )
    
    def record_suspicious_ip(self, ip_address: str, reason: str):
        """Record suspicious IP activity"""
        with self._lock:
            self._suspicious_ips[ip_address] += 1
            
            if self._suspicious_ips[ip_address] >= self.SUSPICIOUS_IP_THRESHOLD:
                self._create_alert(
                    "suspicious_ip_activity",
                    SeverityLevel.MEDIUM,
                    f"Suspicious activity from IP {ip_address}",
                    {
                        'ip_address': ip_address,
                        'reason': reason,
                        'incident_count': self._suspicious_ips[ip_address]
                    }
                )
    
    def record_rate_limit_violation(self, identifier: str, ip_address: str):
        """Record rate limit violation"""
        self._create_alert(
            "rate_limit_violation",
            SeverityLevel.MEDIUM,
            f"Rate limit exceeded for {identifier}",
            {
                'identifier': identifier,
                'ip_address': ip_address,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def _create_alert(self, alert_type: str, severity: SeverityLevel, message: str, details: Dict[str, Any]):
        """Create security alert"""
        alert = SecurityAlert(alert_type, severity, message, details)
        self._alerts.append(alert)
        
        # Log security alert
        security_logger.warning(
            f"Security Alert: {message}",
            extra={'audit_data': {
                'alert_id': alert.alert_id,
                'alert_type': alert_type,
                'severity': severity.value,
                'details': details
            }}
        )
    
    def get_recent_alerts(self, hours: int = 24) -> List[SecurityAlert]:
        """Get recent security alerts"""
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=hours)
            return [
                alert for alert in self._alerts
                if alert.timestamp > cutoff
            ]
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of security alerts"""
        alerts = self.get_recent_alerts(hours)
        
        alert_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for alert in alerts:
            alert_counts[alert.alert_type] += 1
            severity_counts[alert.severity.value] += 1
        
        return {
            'period_hours': hours,
            'total_alerts': len(alerts),
            'alert_breakdown': dict(alert_counts),
            'severity_breakdown': dict(severity_counts),
            'latest_alert': alerts[-1].timestamp if alerts else None
        }


class AuditService:
    """Main audit service"""
    
    def __init__(self):
        self.activity_tracker = ActivityTracker()
        self.security_monitor = SecurityMonitor()
        self._audit_hooks = defaultdict(list)
    
    def log_audit_event(
        self,
        event_type: AuditEventType,
        severity: SeverityLevel = SeverityLevel.LOW,
        user_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        resource: str = None,
        action: str = None,
        details: Dict[str, Any] = None,
        request: Request = None,
        session_id: str = None,
        success: bool = True,
        error_message: str = None
    ):
        """Log an audit event"""
        
        # Extract request information if provided
        if request:
            if not ip_address:
                ip_address = self._get_client_ip(request)
            if not user_agent:
                user_agent = request.headers.get('User-Agent')
        
        # Create audit event
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            details=details or {},
            timestamp=datetime.now(),
            session_id=session_id,
            success=success,
            error_message=error_message
        )
        
        # Log to audit logger
        audit_logger.info(
            f"Audit Event: {event_type.value}",
            extra={'audit_data': asdict(event)}
        )
        
        # Track user activity
        if user_id:
            self.activity_tracker.record_activity(
                user_id,
                event_type.value,
                {
                    'resource': resource,
                    'action': action,
                    'success': success,
                    'ip_address': ip_address
                }
            )
        
        # Security monitoring
        self._process_security_monitoring(event)
        
        # Execute audit hooks
        self._execute_audit_hooks(event)
    
    def _process_security_monitoring(self, event: AuditEvent):
        """Process event for security monitoring"""
        
        # Monitor failed logins
        if event.event_type == AuditEventType.LOGIN_FAILED and event.user_id and event.ip_address:
            self.security_monitor.record_failed_login(event.user_id, event.ip_address)
        
        # Monitor suspicious activities
        if event.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
            self.security_monitor.record_suspicious_ip(
                event.ip_address or "unknown",
                f"{event.event_type.value}: {event.details.get('reason', 'Unknown')}"
            )
        
        # Monitor rate limit violations
        if event.event_type == AuditEventType.RATE_LIMIT_EXCEEDED:
            self.security_monitor.record_rate_limit_violation(
                event.user_id or event.ip_address or "unknown",
                event.ip_address or "unknown"
            )
    
    def _execute_audit_hooks(self, event: AuditEvent):
        """Execute registered audit hooks"""
        hooks = self._audit_hooks.get(event.event_type, [])
        for hook in hooks:
            try:
                hook(event)
            except Exception as e:
                audit_logger.error(f"Audit hook error: {str(e)}")
    
    def register_audit_hook(self, event_type: AuditEventType, hook: Callable[[AuditEvent], None]):
        """Register a hook to be called when specific audit events occur"""
        self._audit_hooks[event_type].append(hook)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def get_user_activity_report(self, user_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive user activity report"""
        return self.activity_tracker.get_activity_summary(user_id, hours)
    
    def get_security_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive security report"""
        return self.security_monitor.get_alert_summary(hours)
    
    def get_audit_events(
        self,
        user_id: str = None,
        event_type: AuditEventType = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit events (this would typically query a database)"""
        # This is a placeholder - in a real implementation, you would query
        # the audit log database or parse log files
        return []
    
    def export_audit_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "json"
    ) -> str:
        """Export audit logs for a date range"""
        # This is a placeholder for audit log export functionality
        # In a real implementation, you would read from log files or database
        return f"Audit logs exported for {start_date} to {end_date} in {format} format"


# Global audit service instance
audit_service = AuditService()


# Decorator for automatic audit logging
def audit_log(
    event_type: AuditEventType,
    severity: SeverityLevel = SeverityLevel.LOW,
    resource: str = None,
    action: str = None
):
    """Decorator to automatically log audit events for functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_message = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                # Extract user_id and request from function arguments if available
                user_id = kwargs.get('user_id')
                request = kwargs.get('request')
                
                # Log audit event
                audit_service.log_audit_event(
                    event_type=event_type,
                    severity=severity,
                    user_id=user_id,
                    resource=resource,
                    action=action,
                    details={
                        'function': func.__name__,
                        'execution_time': time.time() - start_time,
                        'args_count': len(args),
                        'kwargs_count': len(kwargs)
                    },
                    request=request,
                    success=success,
                    error_message=error_message
                )
        
        return wrapper
    return decorator


# Example audit hooks
def critical_event_hook(event: AuditEvent):
    """Hook for critical security events"""
    if event.severity == SeverityLevel.CRITICAL:
        # In a real implementation, this could send alerts via email, SMS, etc.
        print(f"CRITICAL SECURITY EVENT: {event.event_type.value} - {event.details}")


def admin_action_hook(event: AuditEvent):
    """Hook for admin actions"""
    if event.event_type in [AuditEventType.USER_CREATE, AuditEventType.USER_DELETE, AuditEventType.PERMISSION_CHANGE]:
        # Log admin actions to a separate system
        print(f"ADMIN ACTION: {event.event_type.value} by {event.user_id}")


# Register default hooks
audit_service.register_audit_hook(AuditEventType.SECURITY_VIOLATION, critical_event_hook)
audit_service.register_audit_hook(AuditEventType.USER_CREATE, admin_action_hook)
audit_service.register_audit_hook(AuditEventType.USER_DELETE, admin_action_hook)
audit_service.register_audit_hook(AuditEventType.PERMISSION_CHANGE, admin_action_hook)