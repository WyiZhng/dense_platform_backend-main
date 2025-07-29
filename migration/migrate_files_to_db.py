#!/usr/bin/env python3
"""
文件数据迁移脚本：将头像和结果图片文件导入数据库

此脚本将：
1. 将 storage_backup/avatars 中的头像文件导入到 avatars 表
2. 将 storage_backup/reports/Result_image 中的结果图片导入到 result_imgs 表
3. 更新 dense_image 表以关联结果图片
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from database.table import Avatar, ResultImage, DenseImage, DenseReport, User
from database.db import engine
import logging
from pathlib import Path
import re
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建数据库会话
Session = sessionmaker(bind=engine)

def get_file_format(filename):
    """从文件名获取格式"""
    return filename.split('.')[-1].lower() if '.' in filename else 'jpg'

def migrate_avatars():
    """迁移头像文件到数据库"""
    avatar_dir = Path("storage_backup/avatars")
    
    if not avatar_dir.exists():
        logger.warning(f"头像目录不存在: {avatar_dir}")
        return 0
    
    session = Session()
    migrated_count = 0
    
    try:
        logger.info(f"开始迁移头像文件从: {avatar_dir}")
        
        for avatar_file in avatar_dir.glob("*"):
            if avatar_file.is_file():
                try:
                    # 从文件名提取用户ID（假设文件名格式为 userid.ext 或 userid_avatar.ext）
                    filename = avatar_file.name
                    user_id = filename.split('.')[0].split('_')[0]
                    
                    # 检查用户是否存在
                    user = session.query(User).filter(User.id == user_id).first()
                    if not user:
                        logger.warning(f"用户 {user_id} 不存在，跳过头像文件: {filename}")
                        continue
                    
                    # 检查是否已经存在该用户的头像
                    existing_avatar = session.query(Avatar).filter(Avatar.user_id == user_id).first()
                    if existing_avatar:
                        logger.info(f"用户 {user_id} 的头像已存在，跳过: {filename}")
                        continue
                    
                    # 读取文件数据
                    with open(avatar_file, 'rb') as f:
                        file_data = f.read()
                    
                    # 创建头像记录
                    avatar = Avatar(
                        user_id=user_id,
                        filename=filename,
                        data=file_data,
                        format=get_file_format(filename),
                        file_size=len(file_data),
                        upload_time=datetime.fromtimestamp(avatar_file.stat().st_mtime)
                    )
                    
                    session.add(avatar)
                    migrated_count += 1
                    logger.info(f"✅ 迁移头像: {filename} -> 用户: {user_id}")
                    
                except Exception as e:
                    logger.error(f"❌ 迁移头像文件失败 {avatar_file}: {str(e)}")
                    continue
        
        session.commit()
        logger.info(f"🎉 头像迁移完成！共迁移 {migrated_count} 个文件")
        return migrated_count
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ 头像迁移失败: {str(e)}")
        return 0
    finally:
        session.close()

def migrate_result_images():
    """迁移结果图片文件到数据库"""
    result_dir = Path("storage_backup/reports/Result_image")
    
    if not result_dir.exists():
        logger.warning(f"结果图片目录不存在: {result_dir}")
        return 0
    
    session = Session()
    migrated_count = 0
    
    try:
        logger.info(f"开始迁移结果图片从: {result_dir}")
        
        for result_file in result_dir.glob("*"):
            if result_file.is_file():
                try:
                    # 从文件名提取报告ID（假设文件名格式为 reportid.ext 或 reportid_result.ext）
                    filename = result_file.name
                    
                    # 尝试从文件名提取报告ID
                    report_id_match = re.search(r'(\d+)', filename)
                    if not report_id_match:
                        logger.warning(f"无法从文件名提取报告ID: {filename}")
                        continue
                    
                    report_id = int(report_id_match.group(1))
                    
                    # 检查报告是否存在
                    report = session.query(DenseReport).filter(DenseReport.id == report_id).first()
                    if not report:
                        logger.warning(f"报告 {report_id} 不存在，跳过结果图片: {filename}")
                        continue
                    
                    # 检查是否已经存在该报告的结果图片
                    existing_result = session.query(ResultImage).filter(ResultImage.report_id == report_id, ResultImage.filename == filename).first()
                    if existing_result:
                        logger.info(f"报告 {report_id} 的结果图片已存在，跳过: {filename}")
                        continue
                    
                    # 读取文件数据
                    with open(result_file, 'rb') as f:
                        file_data = f.read()
                    
                    # 创建结果图片记录
                    result_image = ResultImage(
                        report_id=report_id,
                        filename=filename,
                        data=file_data,
                        format=get_file_format(filename),
                        file_size=len(file_data),
                        created_time=datetime.fromtimestamp(result_file.stat().st_mtime)
                    )
                    
                    session.add(result_image)
                    session.flush()  # 获取ID
                    
                    # 更新或创建 dense_image 记录以关联结果图片
                    dense_image = session.query(DenseImage).filter(
                        DenseImage.report == report_id,
                        DenseImage._type == 1  # ImageType.result
                    ).first()
                    
                    if dense_image:
                        # 更新现有记录
                        dense_image.result_image = result_image.id
                        logger.info(f"✅ 更新 dense_image 记录: 报告 {report_id}")
                    else:
                        # 创建新的 dense_image 记录
                        new_dense_image = DenseImage(
                            report=report_id,
                            result_image=result_image.id,
                            _type=1  # ImageType.result
                        )
                        session.add(new_dense_image)
                        logger.info(f"✅ 创建新的 dense_image 记录: 报告 {report_id}")
                    
                    migrated_count += 1
                    logger.info(f"✅ 迁移结果图片: {filename} -> 报告: {report_id}")
                    
                except Exception as e:
                    logger.error(f"❌ 迁移结果图片失败 {result_file}: {str(e)}")
                    continue
        
        session.commit()
        logger.info(f"🎉 结果图片迁移完成！共迁移 {migrated_count} 个文件")
        return migrated_count
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ 结果图片迁移失败: {str(e)}")
        return 0
    finally:
        session.close()

def verify_migration():
    """验证迁移结果"""
    session = Session()
    
    try:
        # 检查头像数量
        avatar_count = session.query(Avatar).count()
        logger.info(f"数据库中的头像数量: {avatar_count}")
        
        # 检查结果图片数量
        result_count = session.query(ResultImage).count()
        logger.info(f"数据库中的结果图片数量: {result_count}")
        
        # 检查 dense_image 关联
        dense_image_with_result = session.query(DenseImage).filter(DenseImage.result_image.isnot(None)).count()
        logger.info(f"关联了结果图片的 dense_image 记录数量: {dense_image_with_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 验证迁移结果失败: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    logger.info("🚀 开始文件数据迁移...")
    
    # 检查目录是否存在
    base_dir = Path("storage_backup")
    if not base_dir.exists():
        logger.error(f"❌ 备份目录不存在: {base_dir}")
        logger.info("请确保 storage_backup 目录存在并包含以下子目录：")
        logger.info("  - avatars/")
        logger.info("  - reports/Result_image/")
        sys.exit(1)
    
    total_migrated = 0
    
    # 迁移头像
    avatar_count = migrate_avatars()
    total_migrated += avatar_count
    
    # 迁移结果图片
    result_count = migrate_result_images()
    total_migrated += result_count
    
    # 验证迁移结果
    if verify_migration():
        logger.info(f"🎉 文件数据迁移完成！共迁移 {total_migrated} 个文件")
        logger.info(f"  - 头像: {avatar_count} 个")
        logger.info(f"  - 结果图片: {result_count} 个")
    else:
        logger.error("❌ 迁移验证失败")
        sys.exit(1)