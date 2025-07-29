#!/usr/bin/env python3
"""
数据库迁移脚本：创建头像表和结果图片表

此脚本将创建以下新表：
1. avatars - 存储用户头像
2. result_imgs - 存储报告结果图片
3. 修改 dense_image 表以支持结果图片关联
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.table import Base, Avatar, ResultImage, DenseImage
from database.db import engine
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_new_tables():
    """创建新的数据库表"""
    try:
        logger.info("开始创建新的数据库表...")
        
        # 创建所有表（只会创建不存在的表）
        Base.metadata.create_all(engine)
        
        logger.info("✅ 成功创建新表：avatars, result_imgs")
        
        # 检查是否需要修改 dense_image 表
        with engine.begin() as conn:  # 使用 begin() 来自动处理事务
            # 检查 dense_image 表是否已有 result_image 列
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'dense_image' 
                AND COLUMN_NAME = 'result_image'
            """))
            
            if not result.fetchone():
                logger.info("添加 result_image 列到 dense_image 表...")
                conn.execute(text("""
                    ALTER TABLE dense_image 
                    ADD COLUMN result_image BIGINT(20) NULL,
                    ADD INDEX idx_dense_image_result (result_image),
                    ADD CONSTRAINT fk_dense_image_result 
                    FOREIGN KEY (result_image) REFERENCES result_imgs(id)
                """))
                logger.info("✅ 成功添加 result_image 列")
            else:
                logger.info("result_image 列已存在，跳过修改")
        
        logger.info("🎉 数据库表创建完成！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建数据库表失败: {str(e)}")
        return False

def verify_tables():
    """验证表是否创建成功"""
    try:
        with engine.connect() as conn:
            # 检查 avatars 表
            result = conn.execute(text("SHOW TABLES LIKE 'avatars'"))
            if result.fetchone():
                logger.info("✅ avatars 表创建成功")
            else:
                logger.error("❌ avatars 表创建失败")
                return False
            
            # 检查 result_imgs 表
            result = conn.execute(text("SHOW TABLES LIKE 'result_imgs'"))
            if result.fetchone():
                logger.info("✅ result_imgs 表创建成功")
            else:
                logger.error("❌ result_imgs 表创建失败")
                return False
            
            # 检查 dense_image 表的 result_image 列
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'dense_image' 
                AND COLUMN_NAME = 'result_image'
            """))
            if result.fetchone():
                logger.info("✅ dense_image 表的 result_image 列创建成功")
            else:
                logger.error("❌ dense_image 表的 result_image 列创建失败")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 验证表结构失败: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("🚀 开始数据库表创建迁移...")
    
    if create_new_tables():
        if verify_tables():
            logger.info("🎉 数据库迁移完成！")
            sys.exit(0)
        else:
            logger.error("❌ 表验证失败")
            sys.exit(1)
    else:
        logger.error("❌ 数据库迁移失败")
        sys.exit(1)