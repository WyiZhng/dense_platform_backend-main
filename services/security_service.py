"""
Security Service

This module provides enhanced security features including:
- Secure password hashing with bcrypt
- Rate limiting for authentication attempts
- Input validation and sanitization
- Security monitoring and logging
"""

import bcrypt
import re
import time
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
from fastapi import Request, HTTPException
from pydantic import BaseModel, validator
import hashlib
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
security_logger = logging.getLogger("security")


class SecurityConfig:
    """Security configuration constants"""
    
    # Rate limiting settings
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_WINDOW_MINUTES = 15
    MAX_REQUESTS_PER_MINUTE = 60
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    
    # Session settings
    SESSION_TIMEOUT_HOURS = 24
    MAX_SESSIONS_PER_USER = 5
    
    # Input validation
    MAX_USERNAME_LENGTH = 50
    MAX_NAME_LENGTH = 100
    MAX_EMAIL_LENGTH = 254


class PasswordHasher:
    """Secure password hashing using bcrypt"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)  # 12 rounds for good security/performance balance
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            password: Plain text password
            hashed_password: Stored hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            security_logger.warning(f"Password verification error: {str(e)}")
            return False
    
    @staticmethod
    def is_bcrypt_hash(password_hash: str) -> bool:
        """
        Check if a password hash is a bcrypt hash
        
        Args:
            password_hash: Password hash to check
            
        Returns:
            True if bcrypt hash, False otherwise
        """
        return password_hash.startswith('$2b$') or password_hash.startswith('$2a$') or password_hash.startswith('$2y$')


class PasswordValidator:
    """Password strength validation"""
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """
        Validate password strength
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        
        # Length check
        if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
            errors.append(f"密码长度至少需要 {SecurityConfig.MIN_PASSWORD_LENGTH} 位")
        
        if len(password) > SecurityConfig.MAX_PASSWORD_LENGTH:
            errors.append(f"密码长度不能超过 {SecurityConfig.MAX_PASSWORD_LENGTH} 位")
        
        # Character requirements
        if SecurityConfig.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("密码必须包含至少一个大写字母")
        
        if SecurityConfig.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("密码必须包含至少一个小写字母")
        
        if SecurityConfig.REQUIRE_DIGITS and not re.search(r'\d', password):
            errors.append("密码必须包含至少一个数字")
        
        if SecurityConfig.REQUIRE_SPECIAL_CHARS and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("密码必须包含至少一个特殊字符")
        
        # Common password patterns
        if password.lower() in ['password', '123456', 'qwerty', 'admin', 'root']:
            errors.append("密码过于简单，请使用更复杂的密码")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'strength_score': PasswordValidator._calculate_strength_score(password)
        }
    
    @staticmethod
    def _calculate_strength_score(password: str) -> int:
        """
        Calculate password strength score (0-100)
        
        Args:
            password: Password to score
            
        Returns:
            Strength score
        """
        score = 0
        
        # Length bonus
        score += min(len(password) * 2, 25)
        
        # Character variety bonus
        if re.search(r'[a-z]', password):
            score += 10
        if re.search(r'[A-Z]', password):
            score += 10
        if re.search(r'\d', password):
            score += 10
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 15
        
        # Pattern penalties
        if re.search(r'(.)\1{2,}', password):  # Repeated characters
            score -= 10
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):  # Sequential numbers
            score -= 10
        if re.search(r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password.lower()):  # Sequential letters
            score -= 10
        
        return max(0, min(100, score))


class InputValidator:
    """Input validation and sanitization"""
    
    @staticmethod
    def validate_username(username: str) -> Dict[str, Any]:
        """
        Validate username
        
        Args:
            username: Username to validate
            
        Returns:
            Validation result
        """
        errors = []
        
        if not username:
            errors.append("用户名不能为空")
        elif len(username) > SecurityConfig.MAX_USERNAME_LENGTH:
            errors.append(f"用户名长度不能超过 {SecurityConfig.MAX_USERNAME_LENGTH} 位")
        elif not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append("用户名只能包含字母、数字、下划线和连字符")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'sanitized': InputValidator.sanitize_string(username)
        }
    
    @staticmethod
    def validate_email(email: str) -> Dict[str, Any]:
        """
        Validate email address
        
        Args:
            email: Email to validate
            
        Returns:
            Validation result
        """
        errors = []
        
        if email and len(email) > SecurityConfig.MAX_EMAIL_LENGTH:
            errors.append(f"邮箱长度不能超过 {SecurityConfig.MAX_EMAIL_LENGTH} 位")
        elif email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("邮箱格式不正确")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'sanitized': InputValidator.sanitize_string(email) if email else None
        }
    
    @staticmethod
    def validate_name(name: str) -> Dict[str, Any]:
        """
        Validate name field
        
        Args:
            name: Name to validate
            
        Returns:
            Validation result
        """
        errors = []
        
        if name and len(name) > SecurityConfig.MAX_NAME_LENGTH:
            errors.append(f"姓名长度不能超过 {SecurityConfig.MAX_NAME_LENGTH} 位")
        elif name and not re.match(r'^[a-zA-Z\u4e00-\u9fff\s.-]+$', name):
            errors.append("姓名只能包含字母、中文、空格、点和连字符")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'sanitized': InputValidator.sanitize_string(name) if name else None
        }
    
    @staticmethod
    def sanitize_string(input_str: str) -> str:
        """
        Sanitize string input
        
        Args:
            input_str: String to sanitize
            
        Returns:
            Sanitized string
        """
        if not input_str:
            return input_str
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', input_str)
        
        # Trim whitespace
        sanitized = sanitized.strip()
        
        return sanitized


class RateLimiter:
    """Rate limiting for authentication attempts"""
    
    def __init__(self):
        self._attempts = defaultdict(list)
        self._blocked_ips = defaultdict(datetime)
        self._lock = Lock()
    
    def is_rate_limited(self, identifier: str, max_attempts: int = None, window_minutes: int = None) -> bool:
        """
        Check if an identifier is rate limited
        
        Args:
            identifier: IP address or username
            max_attempts: Maximum attempts allowed
            window_minutes: Time window in minutes
            
        Returns:
            True if rate limited, False otherwise
        """
        max_attempts = max_attempts or SecurityConfig.MAX_LOGIN_ATTEMPTS
        window_minutes = window_minutes or SecurityConfig.LOGIN_WINDOW_MINUTES
        
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=window_minutes)
            
            # Clean old attempts
            self._attempts[identifier] = [
                attempt_time for attempt_time in self._attempts[identifier]
                if attempt_time > cutoff
            ]
            
            # Check if blocked
            if identifier in self._blocked_ips:
                if now < self._blocked_ips[identifier]:
                    return True
                else:
                    del self._blocked_ips[identifier]
            
            # Check attempt count
            if len(self._attempts[identifier]) >= max_attempts:
                # Block for double the window time
                self._blocked_ips[identifier] = now + timedelta(minutes=window_minutes * 2)
                security_logger.warning(f"Rate limit exceeded for {identifier}")
                return True
            
            return False
    
    def record_attempt(self, identifier: str):
        """
        Record an authentication attempt
        
        Args:
            identifier: IP address or username
        """
        with self._lock:
            self._attempts[identifier].append(datetime.now())
    
    def clear_attempts(self, identifier: str):
        """
        Clear attempts for an identifier (on successful login)
        
        Args:
            identifier: IP address or username
        """
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]
            if identifier in self._blocked_ips:
                del self._blocked_ips[identifier]


class SecurityService:
    """Main security service"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.password_hasher = PasswordHasher()
        self.password_validator = PasswordValidator()
        self.input_validator = InputValidator()
    
    def check_authentication_rate_limit(self, request: Request) -> bool:
        """
        Check if authentication request is rate limited
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if rate limited, False otherwise
        """
        ip_address = self.get_client_ip(request)
        return self.rate_limiter.is_rate_limited(ip_address)
    
    def record_authentication_attempt(self, request: Request, username: str = None):
        """
        Record an authentication attempt
        
        Args:
            request: FastAPI request object
            username: Username if available
        """
        ip_address = self.get_client_ip(request)
        self.rate_limiter.record_attempt(ip_address)
        
        if username:
            self.rate_limiter.record_attempt(f"user:{username}")
    
    def clear_authentication_attempts(self, request: Request, username: str):
        """
        Clear authentication attempts on successful login
        
        Args:
            request: FastAPI request object
            username: Username
        """
        ip_address = self.get_client_ip(request)
        self.rate_limiter.clear_attempts(ip_address)
        self.rate_limiter.clear_attempts(f"user:{username}")
    
    def get_client_ip(self, request: Request) -> str:
        """
        Get client IP address from request
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address
        """
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def validate_registration_input(self, username: str, password: str, email: str = None, name: str = None) -> Dict[str, Any]:
        """
        Validate registration input
        
        Args:
            username: Username
            password: Password
            email: Email (optional)
            name: Name (optional)
            
        Returns:
            Validation result
        """
        errors = []
        
        # Validate username
        username_result = self.input_validator.validate_username(username)
        if not username_result['is_valid']:
            errors.extend(username_result['errors'])
        
        # Validate password
        password_result = self.password_validator.validate_password(password)
        if not password_result['is_valid']:
            errors.extend(password_result['errors'])
        
        # Validate email if provided
        if email:
            email_result = self.input_validator.validate_email(email)
            if not email_result['is_valid']:
                errors.extend(email_result['errors'])
        
        # Validate name if provided
        if name:
            name_result = self.input_validator.validate_name(name)
            if not name_result['is_valid']:
                errors.extend(name_result['errors'])
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'password_strength': password_result.get('strength_score', 0)
        }
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], request: Request = None):
        """
        Log security events
        
        Args:
            event_type: Type of security event
            details: Event details
            request: FastAPI request object (optional)
        """
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': details
        }
        
        if request:
            log_data.update({
                'ip_address': self.get_client_ip(request),
                'user_agent': request.headers.get('User-Agent'),
                'path': str(request.url.path),
                'method': request.method
            })
        
        security_logger.info(f"Security Event: {log_data}")


# Global security service instance
security_service = SecurityService()