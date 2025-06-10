# coding: utf-8
import enum

from sqlalchemy import CHAR, Column, Date, DateTime, Enum, ForeignKey, LargeBinary, String, text, Text
from sqlalchemy.dialects.mysql import BIGINT
<<<<<<< HEAD
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class UserType(enum.IntEnum):
=======
#BIGINT 定义大整数类型（适合MySQL），relationship 和 backref 用于定义表间关系。
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import DateTime
from sqlalchemy.sql import func
#from db import engine
from sqlalchemy import create_engine
Base = declarative_base()#创建了一个基类返回给base
metadata = Base.metadata#将 Base 的元数据属性赋值给变量 metadata，这样就可以直接通过 metadata 访问和操作所有相关模型的元数据

eng = create_engine("mysql+pymysql://root:root@localhost/dense_platform?charset=utf8")



class UserType(enum.IntEnum):#账号类型
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    Patient = 0
    Doctor = 1


<<<<<<< HEAD
class ImageType(enum.IntEnum):
=======
class ImageType(enum.IntEnum):#图像
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
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
<<<<<<< HEAD
    format = Column(String(25), server_default=text("jpg"))
=======
    format = Column(String(25), server_default=text("'jpg'"))
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a


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


<<<<<<< HEAD
class Doctor(Base):
=======
class Doctor(User):
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    __tablename__ = 'doctor'

    id = Column(ForeignKey('user.id'), primary_key=True)
    position = Column(String(20))
    workplace = Column(String(20))
<<<<<<< HEAD
    user = relationship('User', backref=backref('user'))
=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a


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
<<<<<<< HEAD
    submitTime = Column(Date, server_default=text("current_timestamp()"))
=======
    submitTime = Column(DateTime, server_default=func.now())
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    current_status = Column(Enum(ReportStatus), server_default=text("'Checking'"))
    diagnose = Column(Text)
    user1 = relationship('User', primaryjoin='DenseReport.doctor == User.id')
    user2 = relationship('User', primaryjoin='DenseReport.user == User.id')


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(BIGINT(20), primary_key=True)
    report = Column(ForeignKey('dense_report.id'), nullable=False, index=True)
<<<<<<< HEAD
    user = Column(ForeignKey("user.id"), nullable=False)
    content = Column(String(4096))
    user1 = relationship('User')
    dense_report = relationship('DenseReport')
=======
    user = Column(ForeignKey("user.id"),nullable=False)
    content = Column(String(4096))
    user1 = relationship('User')
    dense_report = relationship('DenseReport')


Base.metadata.create_all(eng)
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
