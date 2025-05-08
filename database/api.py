from datetime import datetime
from typing import List, Optional

import json
from .storage import (
    load_accounts, save_accounts, load_user_detail, save_user_detail,
    save_image, load_image, save_report, load_report, get_user_reports,
    save_user_avatar
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
    report_id = save_report(report)
    report['id'] = report_id
    return report

def get_reports(id: str) -> List[dict]:
    return get_user_reports(id)

def queryInfo(username: str) -> Optional[dict]:
    return load_user_detail(username)

def deleteInfo(username: str):
    detail_file = f"storage/users/details/{username}.json"
    try:
        os.remove(detail_file)
    except FileNotFoundError:
        pass
    
def uploadImage(file_name: str, data: bytes) -> str:
    format = file_name.split(".")[-1]
    return save_image(data, format)

#新增上传头像
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
