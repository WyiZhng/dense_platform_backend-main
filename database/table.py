# coding: utf-8
import enum
from datetime import datetime

from sqlalchemy import CHAR, Column, Date, DateTime, Enum, ForeignKey, LargeBinary, String, text, Text, Boolean, Index
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class UserType(enum.IntEnum):
    Patient = 0
    Doctor = 1


class ImageType(enum.IntEnum):
    source = 0
    result = 1


class UserSex(enum.IntEnum):
    Female = 0
    Male = 1


class ReportStatus(enum.IntEnum):  #不用IntEnum返回json会是字符串
    Checking = 0
    Completed = 1
    Abnormality = 2
    Error = 3


class Image(Base):
    __tablename__ = 'image'

    id = Column(BIGINT(20), primary_key=True)
    data = Column(LargeBinary(4294967295), nullable=False)
    upload_time = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    format = Column(String(25), server_default=text("'jpg'"))


class Avatar(Base):
    __tablename__ = 'avatars'

    id = Column(BIGINT(20), primary_key=True)
    # 修改外键字段长度以匹配User表的id字段
    user_id = Column(String(50), ForeignKey('user.id'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    data = Column(LargeBinary(4294967295), nullable=False)
    format = Column(String(25), nullable=False, default='jpg')
    upload_time = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    file_size = Column(BIGINT(20), nullable=True)
    
    # Relationships
    user = relationship('User', backref=backref('avatar', uselist=False))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_avatar_user_id', 'user_id'),
        Index('idx_avatar_upload_time', 'upload_time'),
    )


class ResultImage(Base):
    __tablename__ = 'result_imgs'

    id = Column(BIGINT(20), primary_key=True)
    report_id = Column(BIGINT(20), ForeignKey('dense_report.id'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    data = Column(LargeBinary(4294967295), nullable=False)
    format = Column(String(25), nullable=False, default='jpg')
    created_time = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    file_size = Column(BIGINT(20), nullable=True)
    
    # Relationships
    report = relationship('DenseReport', backref=backref('result_images', uselist=True))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_result_image_report_id', 'report_id'),
        Index('idx_result_image_created_time', 'created_time'),
    )


class DenseImage(Base):
    __tablename__ = 'dense_image'

    id = Column(BIGINT(20), primary_key=True)
    report = Column(ForeignKey('dense_report.id'), nullable=False, index=True)
    image = Column(ForeignKey('image.id'), nullable=True, index=True)  # 用户上传的原始图片
    result_image = Column(ForeignKey('result_imgs.id'), nullable=True, index=True)  # 检测结果图片
    _type = Column(Enum(ImageType), nullable=False)
    
    # Relationships
    dense_report = relationship('DenseReport', backref=backref('dense_image', uselist=True),
                                cascade="all, delete-orphan", single_parent=True)
    image_relationship = relationship('Image', foreign_keys=[image], cascade="all, delete-orphan", single_parent=True)
    result_image_relationship = relationship('ResultImage', foreign_keys=[result_image])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_dense_image_report', 'report'),
        Index('idx_dense_image_type', '_type'),
        Index('idx_dense_image_image', 'image'),
        Index('idx_dense_image_result', 'result_image'),
    )


class User(Base):
    __tablename__ = 'user'

    # 增加用户ID长度以支持微信OpenID（28字符）
    id = Column(String(50), primary_key=True)
    password = Column(CHAR(64), nullable=True)  # 微信登录用户可能没有密码
    type = Column(Enum(UserType), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    # 微信登录相关字段
    openid = Column(String(64), nullable=True, unique=True, index=True)  # 微信用户唯一标识
    unionid = Column(String(64), nullable=True, index=True)  # 微信开放平台唯一标识
    username = Column(String(50), nullable=True, index=True)  # 用户名（可选）
    user_id = Column(BIGINT(20), nullable=False, autoincrement=True, unique=True)  # 内部用户ID
    created_time = Column(DateTime, nullable=True)  # 创建时间（兼容字段）
    last_login_time = Column(DateTime, nullable=True)  # 最后登录时间（兼容字段）
    # 隐私授权相关字段
    privacy_consent = Column(Boolean, nullable=True, default=None)  # 隐私授权状态：None=未询问，True=同意，False=拒绝
    privacy_consent_time = Column(DateTime, nullable=True)  # 隐私授权时间
    
    # Relationships
    roles = relationship('Role', secondary='user_role', back_populates='users')
    sessions = relationship('UserSession', back_populates='user', cascade="all, delete-orphan")
    audit_logs = relationship('AuditLog', back_populates='user', cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_type_active', 'type', 'is_active'),
        Index('idx_user_last_login', 'last_login'),
        Index('idx_user_created_at', 'created_at'),
    )


class Role(Base):
    __tablename__ = 'role'

    id = Column(BIGINT(20), primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    
    # Relationships
    users = relationship('User', secondary='user_role', back_populates='roles')
    permissions = relationship('Permission', secondary='role_permission', back_populates='roles')


class UserRole(Base):
    __tablename__ = 'user_role'

    # 修改外键字段长度以匹配User表的id字段
    user_id = Column(String(50), ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    role_id = Column(BIGINT(20), ForeignKey('role.id', ondelete='CASCADE'), primary_key=True)


class Doctor(Base):
    __tablename__ = 'doctor'

    id = Column(String(50), ForeignKey('user.id'), primary_key=True)
    position = Column(String(20))
    workplace = Column(String(20))
    description = Column(Text)
    # 修复backref名称冲突，使用更具体的名称
    user = relationship('User', backref=backref('doctor_profile', uselist=False))


class UserDetail(Base):
    __tablename__ = 'user_detail'

    id = Column(String(50), ForeignKey('user.id'), primary_key=True)
    user_id = Column(BIGINT(20), ForeignKey('user.user_id'), nullable=True, index=True)  # 支持新的user_id关联
    name = Column(String(20))
    sex = Column(Enum(UserSex))
    birth = Column(Date)
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(String(100))
    avatar = Column(ForeignKey('image.id'), index=True)
    avatar_url = Column(String(500), nullable=True)  # 微信头像URL
    created_time = Column(DateTime, nullable=True)  # 创建时间

    # 明确指定使用id字段作为外键，解决多外键路径冲突问题
    user = relationship('User', foreign_keys=[id], backref=backref('user_detail', uselist=False))
    image = relationship('Image')


class DenseReport(Base):
    __tablename__ = 'dense_report'

    id = Column(BIGINT(20), primary_key=True, autoincrement=True, nullable=False)
    user = Column(String(50), ForeignKey('user.id'), index=True)  # 保留用户外键约束
    doctor = Column(String(50), index=True)  # 删除医生外键约束，改为普通字符串字段
    submitTime = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))  # 修改为DateTime类型，精确到小时分钟
    current_status = Column(Enum(ReportStatus), server_default=text("'Checking'"))
    diagnose = Column(Text)
    
    # 只保留用户关系映射，删除医生关系映射
    user2 = relationship('User', primaryjoin='DenseReport.user == User.id')
    
    # Indexes for performance - 保留所有索引以提高查询性能
    __table_args__ = (
        Index('idx_report_user_status', 'user', 'current_status'),
        Index('idx_report_doctor_status', 'doctor', 'current_status'),
        Index('idx_report_submit_time', 'submitTime'),
        Index('idx_report_status_time', 'current_status', 'submitTime'),
    )


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(BIGINT(20), primary_key=True, autoincrement=True)
    report = Column(ForeignKey('dense_report.id'), nullable=False, index=True)
    user = Column(String(50), ForeignKey("user.id"), nullable=False)
    content = Column(String(4096))
    #parent_id = Column(BIGINT(20), ForeignKey('comments.id'), nullable=True, index=True)  # Field doesn't exist in current database
    is_deleted = Column(Boolean, nullable=False, default=False)
    comment_type = Column(String(50), nullable=False, default='general')  # general, diagnosis, collaboration, system
    priority = Column(String(20), nullable=False, default='normal')  # low, normal, high, urgent
    is_resolved = Column(Boolean, nullable=False, default=False)
    resolved_by = Column(String(50), ForeignKey("user.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    
    # Relationships
    user1 = relationship('User', foreign_keys=[user])
    resolver = relationship('User', foreign_keys=[resolved_by])
    dense_report = relationship('DenseReport')
    # parent = relationship('Comment', remote_side=[id], backref='replies')  # Disabled because parent_id field doesn't exist
    
    # Indexes for performance
    __table_args__ = (
        # Index('idx_comment_report_parent', 'report', 'parent_id'),  # parent_id field doesn't exist
        Index('idx_comment_report', 'report'),
        Index('idx_comment_user_created', 'user', 'created_at'),
        Index('idx_comment_type_priority', 'comment_type', 'priority'),
    )


class UserSession(Base):
    __tablename__ = 'user_session'

    id = Column(String(64), primary_key=True)
    # 修改外键字段长度以匹配User表的id字段
    user_id = Column(String(50), ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    token = Column(String(512), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    last_accessed = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(String(512), nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='sessions')
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_session_user_active', 'user_id', 'is_active'),
        Index('idx_user_session_token', 'token'),
        Index('idx_user_session_expires', 'expires_at'),
    )


class Permission(Base):
    __tablename__ = 'permission'

    id = Column(BIGINT(20), primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    
    # Relationships
    roles = relationship('Role', secondary='role_permission', back_populates='permissions')
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_permission_resource_action', 'resource', 'action'),
        Index('idx_permission_name', 'name'),
    )


class RolePermission(Base):
    __tablename__ = 'role_permission'

    role_id = Column(BIGINT(20), ForeignKey('role.id', ondelete='CASCADE'), primary_key=True)
    permission_id = Column(BIGINT(20), ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True)
    granted_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    # 修改外键字段长度以匹配User表的id字段
    granted_by = Column(String(50), ForeignKey('user.id'), nullable=True)


class AuditLog(Base):
    __tablename__ = 'audit_log'

    id = Column(BIGINT(20), primary_key=True, autoincrement=True)
    # 修改外键字段长度以匹配User表的id字段
    user_id = Column(String(50), ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    old_values = Column(Text, nullable=True)  # JSON string of old values
    new_values = Column(Text, nullable=True)  # JSON string of new values
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    timestamp = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='audit_logs')
    
    # Indexes for performance and querying
    __table_args__ = (
        Index('idx_audit_log_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_log_action', 'action'),
        Index('idx_audit_log_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_log_timestamp', 'timestamp'),
    )