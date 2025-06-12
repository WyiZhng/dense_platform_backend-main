from datetime import datetime
from typing import List, Optional

import json
from .storage import (
    load_accounts, save_accounts, load_user_detail, save_user_detail,
    save_image, load_image, save_report, load_report, get_user_reports,save_user_avatar
)
from .table import UserType, UserDetail, DenseReport, ReportStatus


def isDoctor(user: str) -> bool:
    accounts = load_accounts()
    return accounts.get(user, {}).get('type') == UserType.Doctor

def addReport(user: str, doctor: str) -> dict:
    report = {
        'user': user,
        'doctor': doctor,
        'submitTime': datetime.now().isoformat(),
        'current_status': ReportStatus.Checking,
        'diagnose': None
    }
    report['id'] = report_id

def get_reports(id: str) -> List[dict]:
    return get_user_reports(id)


def queryInfo(username: str) -> Optional[dict]:
    return load_user_detail(username)



def deleteInfo(username: str):
    try:
        os.remove(detail_file)
    except FileNotFoundError:
        pass
def uploadImage(file_name: str, data: bytes) -> str:
    format = file_name.split(".")[-1]
    return save_image(data, format)

def uploadavatar(user_name: str, file_name: str, data: bytes) -> str:
    format = file_name.split(".")[-1]
    return save_user_avatar(user_name,format,data )

def addInfo(userinfo: dict) -> bool:
    try:
        save_user_detail(userinfo['id'], userinfo)
        return True
    except Exception as e:
        print(f"Error saving user info: {e}")
        return False
def queryAccount(account: str, password: str) -> Optional[dict]:
    accounts = load_accounts()
    user_data = accounts.get(account)
    if user_data and user_data.get('password') == password:
        return user_data
    return None
def addUserAccount(account: str, password: str, _type: UserType) -> bool:
    accounts = load_accounts()
    if account in accounts:
        return False
    accounts[account] = {
        'id': account,
        'password': password,
        'type': _type
    }
    save_accounts(accounts)
    return True

def teechLevel(data_t)-> str:
    label_counts = {
        '0': 0,  # 正常
        '1': 0,  # 轻度
        '2': 0,  # 中度
        '3': 0,  # 重度
        '4': 0,
        '5': 0,
        '6': 0
    }
    data_dict = eval(data_t)

    # 统计每个标签的数量
    for label in data_dict['labels']:
        label_type = label.split()[0]  # 获取标签类型(0,1,2,3)
        label_counts[label_type] += 1
    c = label_counts['4']+label_counts['5']+label_counts['6']
    b = label_counts['3']+label_counts['2']+label_counts['1']
    if c > 0:
        if b>0:
            resu = f"您有 {c} 颗较为严重的龋齿，以及 {b} 颗轻度龋齿，请尽快处理。"
        else:
            resu = f"您有 {c} 颗较为严重的龋齿，请及时治疗。"
    elif b > 0:
        resu = f"您有 {c} 颗较为轻度龋齿，请及时治疗。"
    else:
        resu = f"您的牙齿状态良好！请继续保持！。"
    return resu

def teechLevel2(data_t)-> str:
    label_counts = {
        '0': 0,  # 正常
        '1': 0,  # 轻度
        '2': 0,  # 中度
        '3': 0,  # 重度
        '4': 0,
        '5': 0,
        '6': 0
    }
    # 统计每个标签的数量
    for cls in data_t:
        label_counts[cls] += 1
    c = label_counts['5']+label_counts['6']
    b = label_counts['3']+label_counts['2']+label_counts['4']
    if c > 0:
        if b>0:
            resu = f"您有 {c} 颗较为严重的龋齿，以及 {b} 颗轻度龋齿，请尽快处理。"
        else:
            resu = f"您有 {c} 颗较为严重的龋齿，请及时治疗。"
    elif b > 0:
        resu = f"您有 {b} 颗较为轻度龋齿，请及时治疗。"
    else:
        resu = f"您的牙齿状态良好！请继续保持！。"
    return resu
# from typing import List
#
# import sqlalchemy.exc
# from sqlalchemy import and_
# from sqlalchemy.orm import sessionmaker, Session
#
# from dense_platform_backend_main.database.db import engine
# from dense_platform_backend_main.database.table import UserDetail, DenseReport, User, UserType, Image
#
#
# def isDoctor(_session: Session, user: str) -> bool:
#     u = _session.query(User).filter(User.id == user).first()
#     return u.type == UserType.Doctor
#
#
# def addReport(_session: Session, user: str, doctor: str) -> DenseReport:
#     report = DenseReport(user=user, doctor=doctor)
#     _session.add(report)
#     _session.flush()
#
#     return report
#
#
# def get_reports(_session: Session, id: str) -> List[DenseReport]:
#     reports = _session.query(DenseReport).filter(DenseReport.user == id).all()
#     _session.commit()
#     return reports
#
#
# def queryInfo(_session, username: str) -> UserDetail:
#     user = _session.query(UserDetail).filter(UserDetail.id == username).first()
#     _session.commit()
#     return user
#
#
# def deleteInfo(_session, username: str):
#     user = _session.query(UserDetail).filter(UserDetail.id == username).first()
#     if user is not None:
#         _session.delete(user)
#         _session.commit()
#
#
# def uploadImage(_session: Session, file_name: str, data: bytes) -> int:
#     image = Image(format=file_name.split(".")[-1], data=data)
#     _session.add(image)
#     _session.commit()
#     return image.id
#
#
# def addInfo(_session, userinfo: UserDetail):
#     try:
#         _session.add(userinfo)
#         _session.commit()
#     except sqlalchemy.exc.IntegrityError as err:
#
#         _session.rollback()
#         raise err
#     return True
#
#
# def queryAccount(_session, account: str, password: str) -> User:
#     user = _session.query(User).filter(
#         and_(User.id == account, User.password == password)).first()
#     _session.commit()
#     return user
#
#
# def addUserAccount(_session: Session, account: str, password: str, _type: UserType) -> bool:
#     user = User(id=account, password=password, type=_type)
#     try:
#         _session.add(user)
#         _session.commit()
#     except sqlalchemy.exc.IntegrityError as err:
#
#         _session.rollback()
#         return False
#     return True
#
#
# if __name__ == '__main__':
#     Session = sessionmaker(bind=engine)
#     session = Session()
