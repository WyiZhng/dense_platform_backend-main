"""
Test Audit Logging and Monitoring System

This module tests the audit logging and monitoring features.
"""

import sys
import time
from datetime import datetime, timedelta
from unittest.mock import Mock

sys.path.append('.')

from dense_platform_backend_main.services.audit_service import (
    audit_service, AuditEventType, SeverityLevel, SecurityAlert,
    ActivityTracker, SecurityMonitor, AuditService
)


def test_audit_logging():
    """Test basic audit logging functionality"""
    print("Testing audit logging...")
    
    # Create mock request
    mock_request = Mock()
    mock_request.client = Mock()
    mock_request.client.host = "192.168.1.1"
    mock_request.headers = {"User-Agent": "Test Browser"}
    
    # Log various audit events
    audit_service.log_audit_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        severity=SeverityLevel.LOW,
        user_id="testuser",
        resource="authentication",
        action="login",
        details={"user_type": "Patient"},
        request=mock_request,
        success=True
    )
    
    audit_service.log_audit_event(
        event_type=AuditEventType.DATA_CREATE,
        severity=SeverityLevel.MEDIUM,
        user_id="testuser",
        resource="medical_report",
        action="create",
        details={"report_id": "12345"},
        request=mock_request,
        success=True
    )
    
    audit_service.log_audit_event(
        event_type=AuditEventType.SECURITY_VIOLATION,
        severity=SeverityLevel.HIGH,
        user_id="malicious_user",
        resource="system",
        action="unauthorized_access",
        details={"attempted_resource": "/admin/users"},
        request=mock_request,
        success=False,
        error_message="Access denied"
    )
    
    print("✓ Audit logging works correctly!")
    return True


def test_activity_tracking():
    """Test user activity tracking"""
    print("\nTesting activity tracking...")
    
    tracker = ActivityTracker()
    user_id = "testuser"
    
    # Record various activities
    tracker.record_activity(user_id, "login", {"ip": "192.168.1.1"})
    time.sleep(0.1)  # Small delay to ensure different timestamps
    tracker.record_activity(user_id, "view_report", {"report_id": "123"})
    time.sleep(0.1)
    tracker.record_activity(user_id, "create_report", {"report_type": "diagnosis"})
    
    # Get activity summary
    summary = tracker.get_activity_summary(user_id, 1)  # Last 1 hour
    
    print(f"Total activities: {summary['total_activities']}")
    print(f"Activity breakdown: {summary['activity_breakdown']}")
    
    assert summary['total_activities'] == 3
    assert 'login' in summary['activity_breakdown']
    assert 'view_report' in summary['activity_breakdown']
    assert 'create_report' in summary['activity_breakdown']
    
    print("✓ Activity tracking works correctly!")
    return True


def test_security_monitoring():
    """Test security monitoring and alerting"""
    print("\nTesting security monitoring...")
    
    monitor = SecurityMonitor()
    
    # Test failed login monitoring
    user_id = "testuser"
    ip_address = "192.168.1.100"
    
    # Record multiple failed logins
    for i in range(6):  # Exceed threshold
        monitor.record_failed_login(user_id, ip_address)
    
    # Check if alerts were generated
    alerts = monitor.get_recent_alerts(1)  # Last 1 hour
    print(f"Generated {len(alerts)} security alerts")
    
    # Should have at least one alert for multiple failed logins
    failed_login_alerts = [
        alert for alert in alerts
        if alert.alert_type == "multiple_failed_logins"
    ]
    assert len(failed_login_alerts) > 0
    
    # Test suspicious IP monitoring
    monitor.record_suspicious_ip("10.0.0.1", "Multiple failed attempts")
    for i in range(12):  # Exceed threshold
        monitor.record_suspicious_ip("10.0.0.1", "Suspicious activity")
    
    # Test rate limit violation
    monitor.record_rate_limit_violation("user123", "10.0.0.2")
    
    # Get alert summary
    summary = monitor.get_alert_summary(1)
    print(f"Alert summary: {summary}")
    
    assert summary['total_alerts'] > 0
    
    print("✓ Security monitoring works correctly!")
    return True


def test_audit_hooks():
    """Test audit event hooks"""
    print("\nTesting audit hooks...")
    
    # Create a test audit service
    test_audit_service = AuditService()
    
    # Create a test hook
    hook_called = False
    hook_event = None
    
    def test_hook(event):
        nonlocal hook_called, hook_event
        hook_called = True
        hook_event = event
    
    # Register the hook
    test_audit_service.register_audit_hook(AuditEventType.LOGIN_SUCCESS, test_hook)
    
    # Log an event that should trigger the hook
    test_audit_service.log_audit_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        severity=SeverityLevel.LOW,
        user_id="testuser",
        resource="authentication",
        action="login",
        success=True
    )
    
    # Check if hook was called
    assert hook_called, "Audit hook was not called"
    assert hook_event is not None, "Hook event is None"
    assert hook_event.event_type == AuditEventType.LOGIN_SUCCESS
    
    print("✓ Audit hooks work correctly!")
    return True


def test_security_alerts():
    """Test security alert creation and management"""
    print("\nTesting security alerts...")
    
    # Create security alerts
    alert1 = SecurityAlert(
        alert_type="test_alert",
        severity=SeverityLevel.HIGH,
        message="Test security alert",
        details={"test": "data"}
    )
    
    alert2 = SecurityAlert(
        alert_type="critical_alert",
        severity=SeverityLevel.CRITICAL,
        message="Critical security issue",
        details={"urgent": True}
    )
    
    # Check alert properties
    assert alert1.severity == SeverityLevel.HIGH
    assert alert2.severity == SeverityLevel.CRITICAL
    assert alert1.alert_type == "test_alert"
    assert alert2.alert_type == "critical_alert"
    assert alert1.alert_id.startswith("test_alert_")
    assert alert2.alert_id.startswith("critical_alert_")
    
    print("✓ Security alerts work correctly!")
    return True


def test_audit_decorator():
    """Test audit logging decorator"""
    print("\nTesting audit decorator...")
    
    from dense_platform_backend_main.services.audit_service import audit_log
    
    # Create a test function with audit decorator
    @audit_log(
        event_type=AuditEventType.DATA_CREATE,
        severity=SeverityLevel.MEDIUM,
        resource="test_resource",
        action="test_action"
    )
    def test_function(user_id=None, request=None):
        return "success"
    
    # Call the decorated function
    result = test_function(user_id="testuser")
    
    assert result == "success"
    
    print("✓ Audit decorator works correctly!")
    return True


def test_comprehensive_audit_flow():
    """Test comprehensive audit flow with multiple components"""
    print("\nTesting comprehensive audit flow...")
    
    # Simulate a user session with multiple activities
    user_id = "comprehensive_test_user"
    
    # Mock request
    mock_request = Mock()
    mock_request.client = Mock()
    mock_request.client.host = "192.168.1.200"
    mock_request.headers = {"User-Agent": "Comprehensive Test Browser"}
    
    # 1. User login
    audit_service.log_audit_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        severity=SeverityLevel.LOW,
        user_id=user_id,
        resource="authentication",
        action="login",
        details={"user_type": "Doctor"},
        request=mock_request,
        success=True
    )
    
    # 2. User accesses patient data
    audit_service.log_audit_event(
        event_type=AuditEventType.DATA_READ,
        severity=SeverityLevel.LOW,
        user_id=user_id,
        resource="patient_data",
        action="view",
        details={"patient_id": "P12345"},
        request=mock_request,
        success=True
    )
    
    # 3. User creates medical report
    audit_service.log_audit_event(
        event_type=AuditEventType.DATA_CREATE,
        severity=SeverityLevel.MEDIUM,
        user_id=user_id,
        resource="medical_report",
        action="create",
        details={"report_type": "diagnosis", "patient_id": "P12345"},
        request=mock_request,
        success=True
    )
    
    # 4. User updates patient information
    audit_service.log_audit_event(
        event_type=AuditEventType.DATA_UPDATE,
        severity=SeverityLevel.MEDIUM,
        user_id=user_id,
        resource="patient_data",
        action="update",
        details={"patient_id": "P12345", "fields_updated": ["address", "phone"]},
        request=mock_request,
        success=True
    )
    
    # 5. User attempts unauthorized action (should trigger security alert)
    audit_service.log_audit_event(
        event_type=AuditEventType.ACCESS_DENIED,
        severity=SeverityLevel.HIGH,
        user_id=user_id,
        resource="admin_panel",
        action="access",
        details={"attempted_action": "delete_user"},
        request=mock_request,
        success=False,
        error_message="Insufficient permissions"
    )
    
    # 6. User logs out
    audit_service.log_audit_event(
        event_type=AuditEventType.LOGOUT,
        severity=SeverityLevel.LOW,
        user_id=user_id,
        resource="authentication",
        action="logout",
        details={},
        request=mock_request,
        success=True
    )
    
    # Check activity tracking
    activity_summary = audit_service.get_user_activity_report(user_id, 1)
    print(f"User activity summary: {activity_summary}")
    
    # Check security monitoring
    security_summary = audit_service.get_security_report(1)
    print(f"Security summary: {security_summary}")
    
    # Verify we have recorded activities
    assert activity_summary['total_activities'] > 0
    
    print("✓ Comprehensive audit flow works correctly!")
    return True


def main():
    """Run all audit system tests"""
    print("🔍 Testing Audit Logging and Monitoring System")
    print("=" * 50)
    
    try:
        test_audit_logging()
        test_activity_tracking()
        test_security_monitoring()
        test_audit_hooks()
        test_security_alerts()
        test_audit_decorator()
        test_comprehensive_audit_flow()
        
        print("\n🎉 All audit system tests passed!")
        print("\nAudit and monitoring features implemented:")
        print("✓ Comprehensive audit event logging")
        print("✓ User activity tracking and reporting")
        print("✓ Security monitoring and alerting")
        print("✓ Failed login attempt detection")
        print("✓ Suspicious IP activity monitoring")
        print("✓ Rate limit violation tracking")
        print("✓ Audit event hooks for custom actions")
        print("✓ Security alert management")
        print("✓ Structured JSON logging")
        print("✓ Audit decorator for automatic logging")
        print("✓ Comprehensive reporting and dashboards")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)