#!/usr/bin/env python3
"""
头像和结果图片迁移测试脚本

此脚本用于测试迁移后的功能是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import sessionmaker
from database.table import Avatar, ResultImage, DenseImage, User, DenseReport
from database.db import engine
from services.database_storage_service import DatabaseStorageService
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建数据库会话
Session = sessionmaker(bind=engine)

def test_avatar_functionality():
    """测试头像功能"""
    logger.info("🧪 测试头像功能...")
    
    session = Session()
    
    try:
        # 获取一个测试用户
        test_user = session.query(User).first()
        if not test_user:
            logger.warning("⚠️  没有找到测试用户")
            return False
        
        user_id = test_user.id
        logger.info(f"使用测试用户: {user_id}")
        
        # 测试获取头像信息
        avatar_info = DatabaseStorageService.get_avatar_info(session, user_id)
        if avatar_info:
            logger.info(f"✅ 找到用户头像: {avatar_info['filename']}")
            logger.info(f"   - 格式: {avatar_info['format']}")
            logger.info(f"   - 大小: {avatar_info['file_size']} bytes")
            logger.info(f"   - 上传时间: {avatar_info['upload_time']}")
            
            # 测试加载头像数据
            avatar_data = DatabaseStorageService.load_avatar(session, user_id)
            if avatar_data:
                logger.info(f"✅ 成功加载头像数据，大小: {len(avatar_data)} bytes")
            else:
                logger.error("❌ 加载头像数据失败")
                return False
        else:
            logger.info(f"ℹ️  用户 {user_id} 没有头像")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试头像功能失败: {str(e)}")
        return False
    finally:
        session.close()

def test_result_image_functionality():
    """测试结果图片功能"""
    logger.info("🧪 测试结果图片功能...")
    
    session = Session()
    
    try:
        # 获取一个测试报告
        test_report = session.query(DenseReport).first()
        if not test_report:
            logger.warning("⚠️  没有找到测试报告")
            return False
        
        report_id = str(test_report.id)
        logger.info(f"使用测试报告: {report_id}")
        
        # 测试获取结果图片
        result_images = DatabaseStorageService.get_report_result_images(session, report_id)
        if result_images:
            logger.info(f"✅ 找到 {len(result_images)} 个结果图片")
            
            for img in result_images:
                logger.info(f"   - 文件名: {img['filename']}")
                logger.info(f"   - 格式: {img['format']}")
                logger.info(f"   - 大小: {img['file_size']} bytes")
                
                # 测试加载结果图片数据
                img_data = DatabaseStorageService.load_result_image(session, img['id'])
                if img_data:
                    logger.info(f"   ✅ 成功加载图片数据，大小: {len(img_data)} bytes")
                else:
                    logger.error(f"   ❌ 加载图片数据失败: {img['id']}")
                    return False
        else:
            logger.info(f"ℹ️  报告 {report_id} 没有结果图片")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试结果图片功能失败: {str(e)}")
        return False
    finally:
        session.close()

def test_dense_image_associations():
    """测试 dense_image 表的关联关系"""
    logger.info("🧪 测试 dense_image 关联关系...")
    
    session = Session()
    
    try:
        # 检查有结果图片关联的记录
        dense_images_with_result = session.query(DenseImage).filter(
            DenseImage.result_image.isnot(None)
        ).all()
        
        logger.info(f"✅ 找到 {len(dense_images_with_result)} 个关联了结果图片的 dense_image 记录")
        
        for dense_img in dense_images_with_result[:5]:  # 只显示前5个
            logger.info(f"   - 报告 {dense_img.report}, 结果图片 {dense_img.result_image}")
        
        # 检查有原始图片关联的记录
        dense_images_with_source = session.query(DenseImage).filter(
            DenseImage.image.isnot(None)
        ).all()
        
        logger.info(f"✅ 找到 {len(dense_images_with_source)} 个关联了原始图片的 dense_image 记录")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试关联关系失败: {str(e)}")
        return False
    finally:
        session.close()

def test_database_integrity():
    """测试数据库完整性"""
    logger.info("🧪 测试数据库完整性...")
    
    session = Session()
    
    try:
        # 检查表是否存在
        avatar_count = session.query(Avatar).count()
        result_count = session.query(ResultImage).count()
        dense_image_count = session.query(DenseImage).count()
        
        logger.info(f"✅ 数据库表统计:")
        logger.info(f"   - avatars: {avatar_count} 条记录")
        logger.info(f"   - result_imgs: {result_count} 条记录")
        logger.info(f"   - dense_image: {dense_image_count} 条记录")
        
        # 检查外键关系
        avatars_with_valid_users = session.query(Avatar).join(User).count()
        results_with_valid_reports = session.query(ResultImage).join(DenseReport).count()
        
        logger.info(f"✅ 外键关系检查:")
        logger.info(f"   - 有效用户的头像: {avatars_with_valid_users}/{avatar_count}")
        logger.info(f"   - 有效报告的结果图片: {results_with_valid_reports}/{result_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库完整性测试失败: {str(e)}")
        return False
    finally:
        session.close()

def main():
    """主测试函数"""
    logger.info("🚀 开始头像和结果图片迁移测试")
    logger.info("=" * 60)
    
    tests = [
        ("数据库完整性", test_database_integrity),
        ("头像功能", test_avatar_functionality),
        ("结果图片功能", test_result_image_functionality),
        ("关联关系", test_dense_image_associations),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"📋 测试: {test_name}")
        if test_func():
            logger.info(f"✅ {test_name} 测试通过")
            passed += 1
        else:
            logger.error(f"❌ {test_name} 测试失败")
        logger.info("-" * 40)
    
    # 测试结果摘要
    logger.info("=" * 60)
    logger.info(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！迁移成功！")
        return True
    else:
        logger.error(f"❌ {total - passed} 个测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)