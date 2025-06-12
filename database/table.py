# coding: utf-8
import enum

from sqlalchemy import CHAR, Column, Date, DateTime, Enum, ForeignKey, LargeBinary, String, text, Text
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
    upload_time = Column(DateTime, nullable=False, server_default=text("current_timestamp()"))
    format = Column(String(25), server_default=text("jpg"))


class DenseImage(Base):
    __tablename__ = 'dense_image'

    id = Column(BIGINT(20), primary_key=True)
    report = Column(ForeignKey('dense_report.id'), nullable=False, index=True)
    image = Column(ForeignKey('image.id'), nullable=False, index=True)
    _type = Column(Enum(ImageType), nullable=False)
    dense_report = relationship('DenseReport', backref=backref('dense_image', uselist=True),
                                cascade="all, delete-orphan", single_parent=True)
    image_relationship = relationship('Image', cascade="all, delete-orphan", single_parent=True)


class User(Base):
    __tablename__ = 'user'

    id = Column(String(20), primary_key=True)
    password = Column(CHAR(64), nullable=False)
    type = Column(Enum(UserType), nullable=False)


class Doctor(Base):
    __tablename__ = 'doctor'

    id = Column(ForeignKey('user.id'), primary_key=True)
    position = Column(String(20))
    workplace = Column(String(20))
    user = relationship('User', backref=backref('user'))


class UserDetail(Base):
    __tablename__ = 'user_detail'

    id = Column(ForeignKey('user.id'), primary_key=True)
    name = Column(String(20))
    sex = Column(Enum(UserSex))
    birth = Column(Date)
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(String(100))
    avatar = Column(ForeignKey('image.id'), index=True)

    user = relationship('User', backref=backref('user_detail', uselist=False))
    image = relationship('Image')


class DenseReport(Base):
    __tablename__ = 'dense_report'

    id = Column(BIGINT(20), primary_key=True)
    user = Column(ForeignKey('user.id'), index=True)
    doctor = Column(ForeignKey('user.id'), index=True)
    submitTime = Column(Date, server_default=text("current_timestamp()"))
    current_status = Column(Enum(ReportStatus), server_default=text("'Checking'"))
    diagnose = Column(Text)
    user1 = relationship('User', primaryjoin='DenseReport.doctor == User.id')
    user2 = relationship('User', primaryjoin='DenseReport.user == User.id')


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(BIGINT(20), primary_key=True)
    report = Column(ForeignKey('dense_report.id'), nullable=False, index=True)
    user = Column(ForeignKey("user.id"), nullable=False)
    content = Column(String(4096))
    user1 = relationship('User')
    dense_report = relationship('DenseReport')
