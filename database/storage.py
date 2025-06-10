import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid
from fastapi import FastAPI, File, UploadFile
<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
STORAGE_ROOT = Path("storage")
USERS_DIR = STORAGE_ROOT / "users"
REPORTS_DIR = STORAGE_ROOT / "reports"
IMAGES_DIR = STORAGE_ROOT / "images"
COMMENTS_DIR = STORAGE_ROOT / "comments"
<<<<<<< HEAD
RESLUTIMG_DIR = REPORTS_DIR / "Result_image"
AVATARS_DIR = STORAGE_ROOT / "avatars"
=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a

# 确保所需目录存在
def init_storage():
    for path in [USERS_DIR, REPORTS_DIR, IMAGES_DIR, COMMENTS_DIR, USERS_DIR / "details"]:
        path.mkdir(parents=True, exist_ok=True)

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
# 用户账号文件操作
def load_accounts() -> Dict:
    account_file = USERS_DIR / "accounts.json"
    if not account_file.exists():
        return {}
    with open(account_file, 'r', encoding='utf-8') as f:
        return json.load(f)

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def save_accounts(accounts: Dict):
    with open(USERS_DIR / "accounts.json", 'w', encoding='utf-8') as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def save_user_avatar(username: str, image_ext: str, image_data: bytes):
    image_path = IMAGES_DIR / f"{username}.{image_ext}"
    with open(image_path, 'wb') as f:
        f.write(image_data)
    return username
<<<<<<< HEAD
=======
    # save_name = f"{username}.{image_ext}"
    #  # 构建保存路径
    # save_path = f"storage/images/{save_name}"
    #     # 确保目录存在
    # os.makedirs("storage/images", exist_ok=True)
    #     # 将图片数据保存到文件
    # with open(save_path, "wb") as f:
    #     f.write(image_data)
    # return save_name
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a


# 用户详细信息操作
def save_user_detail(user_id: str, detail_data: Dict):
    with open(USERS_DIR / "details" / f"{user_id}.json", 'w', encoding='utf-8') as f:
        json.dump(detail_data, f, ensure_ascii=False, indent=2)

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def load_user_detail(user_id: str) -> Optional[Dict]:
    detail_file = USERS_DIR / "details" / f"{user_id}.json"
    if not detail_file.exists():
        return None
    try:
        with open(detail_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"JSON格式错误: {detail_file}")
        return None
    except Exception as e:
        print(f"加载用户详情时出错: {e}")
        return None

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
# 图片操作
def save_image(image_data: bytes, format: str) -> str:
    image_id = str(uuid.uuid4())
    image_path = IMAGES_DIR / f"{image_id}.{format}"
    with open(image_path, 'wb') as f:
        f.write(image_data)
    return image_id

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def load_image(image_id: str) -> Optional[bytes]:
    for ext in ['jpg', 'png', 'jpeg']:
        image_path = IMAGES_DIR / f"{image_id}.{ext}"
        if image_path.exists():
            with open(image_path, 'rb') as f:
                return f.read()
    return None

<<<<<<< HEAD

def load_result_image(image_id: str) -> Optional[bytes]:
    for ext in ['jpg', 'png', 'jpeg']:
        image_path = RESLUTIMG_DIR / f"{image_id}.{ext}"
        if image_path.exists():
            with open(image_path, 'rb') as f:
                return f.read()
    return None

def load_avatars_image(image_id: str) -> Optional[bytes]:
    for ext in ['jpg', 'png', 'jpeg']:
        image_path = AVATARS_DIR / f"{image_id}.{ext}"
        if image_path.exists():
            with open(image_path, 'rb') as f:
                return f.read()
    return None

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
# 报告操作
def save_report(report_data: Dict):
    current_time = datetime.now().strftime("%Y%m%d%H%M")
    report_id = f"{current_time}-{report_data['doctor']}-{report_data['user']}"
    report_data['id'] = report_id
    with open(REPORTS_DIR / f"{report_id}.json", 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    return report_id
<<<<<<< HEAD
def save_report_com(report_data: Dict):
    current_time = datetime.now().strftime("%Y%m%d%H%M")

    report_id = f"{current_time}-{report_data['doctor']}-{report_data['user']}-{'complete'}"
    report_data['id'] = report_id
    with open(REPORTS_DIR / f"{report_id}.json", 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    return report_id
=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a

def load_report(report_id: str) -> Optional[Dict]:
    report_file = REPORTS_DIR / f"{report_id}.json"
    if not report_file.exists():
        return None
    with open(report_file, 'r', encoding='utf-8') as f:
        return json.load(f)

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def get_user_reports(user_id: str,type:int) -> list:
    reports = []
    if type == 0:
        for report_file in REPORTS_DIR.glob("*.json"):
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                if report.get('user') == user_id:
                    reports.append(report)
    else:
        for report_file in REPORTS_DIR.glob("*.json"):
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                if report.get('doctor') == user_id:
                    reports.append(report)
    return reports

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
# 评论操作
def save_comment(report_id: str, comment_data: Dict):
    comment_dir = COMMENTS_DIR / report_id
    comment_dir.mkdir(parents=True, exist_ok=True)
<<<<<<< HEAD

    comment_id = comment_data.get('id', str(uuid.uuid4()))
    comment_data['id'] = comment_id

=======
    
    comment_id = comment_data.get('id', str(uuid.uuid4()))
    comment_data['id'] = comment_id
    
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    with open(comment_dir / f"{comment_id}.json", 'w', encoding='utf-8') as f:
        json.dump(comment_data, f, ensure_ascii=False, indent=2)
    return comment_id

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def get_report_comments(report_id: str) -> list:
    comment_dir = COMMENTS_DIR / report_id
    if not comment_dir.exists():
        return []
<<<<<<< HEAD

=======
        
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    comments = []
    for comment_file in comment_dir.glob("*.json"):
        with open(comment_file, 'r', encoding='utf-8') as f:
            comments.append(json.load(f))
    return comments

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
# 报告图片操作
def save_report_image(report_id: str, image_id: str, image_type: str):
    report = load_report(report_id)
    if report is None:
        return False
<<<<<<< HEAD

=======
        
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    if 'images' not in report:
        report['images'] = {}
    if image_type not in report['images']:
        report['images'][image_type] = []
<<<<<<< HEAD

=======
        
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    report['images'][image_type].append(image_id)
    save_report(report)
    return True

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def get_report_images(report_id: str) -> Dict[str, List[str]]:
    report = load_report(report_id)
    if report is None:
        return {}
    return report.get('images', {})

<<<<<<< HEAD

=======
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
# 更新报告状态
def update_report_status(report_id: str, status: str, diagnose: str = None):
    report = load_report(report_id)
    if report is None:
        return False
<<<<<<< HEAD

    report['current_status'] = status
    if diagnose is not None:
        report['diagnose'] = diagnose

    save_report(report)
    return True


# 在 storage.py 中添加删除报告的功能

=======
        
    report['current_status'] = status
    if diagnose is not None:
        report['diagnose'] = diagnose
        
    save_report(report)
    return True

# 在 storage.py 中添加删除报告的功能
#这边应该添加删除对应照片的功能
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def delete_report(report_id: str) -> bool:
    """删除报告及其相关数据"""
    report_file = REPORTS_DIR / f"{report_id}.json"
    comment_dir = COMMENTS_DIR / report_id
<<<<<<< HEAD

    try:
        if report_file.exists():
            report_file.unlink()

        if comment_dir.exists():
            shutil.rmtree(comment_dir)

=======
    
    try:
        if report_file.exists():
            report_file.unlink()
            
        if comment_dir.exists():
            shutil.rmtree(comment_dir)
            
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
        return True
    except Exception as e:
        print(f"Error deleting report: {e}")
        return False

<<<<<<< HEAD

def save_doctor_info(doctor_id: str, info: Dict):
    doctor_file = USERS_DIR / "doctors" / f"{doctor_id}.json"
    doctor_file.parent.mkdir(parents=True, exist_ok=True)

    with open(doctor_file, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


=======
# 医生信息操作
def save_doctor_info(doctor_id: str, info: Dict):
    doctor_file = USERS_DIR / "doctors" / f"{doctor_id}.json"
    doctor_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(doctor_file, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
def load_doctor_info(doctor_id: str) -> Optional[Dict]:
    doctor_file = USERS_DIR / "doctors" / f"{doctor_id}.json"
    if not doctor_file.exists():
        return None
<<<<<<< HEAD

=======
        
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
    try:
        with open(doctor_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading doctor info: {e}")
        return None

<<<<<<< HEAD

# 初始化存储
init_storage()
=======
# 初始化存储
init_storage() 
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
