#!/usr/bin/env python3
"""
头像和结果图片迁移主脚本

此脚本将执行以下操作：
1. 创建新的数据库表（avatars, result_imgs）
2. 修改现有表结构（dense_image）
3. 将文件数据迁移到数据库
4. 验证迁移结果
"""

import sys
import os
import subprocess
from subprocess import PIPE
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_script(script_path, description):
    """运行迁移脚本"""
    logger.info(f"🚀 开始执行: {description}")
    
    try:
        # 兼容较老版本的Python，使用 stdout=PIPE, stderr=PIPE 替代 capture_output=True
        result = subprocess.run([sys.executable, script_path], 
                              stdout=PIPE, stderr=PIPE, 
                              universal_newlines=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            logger.info(f"✅ {description} 完成")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            logger.error(f"❌ {description} 失败")
            if result.stderr:
                print("错误输出:", result.stderr)
            if result.stdout:
                print("标准输出:", result.stdout)
            return False
            
    except Exception as e:
        logger.error(f"❌ 执行 {description} 时发生异常: {str(e)}")
        return False

def check_prerequisites():
    """检查迁移前提条件"""
    logger.info("🔍 检查迁移前提条件...")
    
    # 检查备份目录
    backup_dir = Path("storage_backup")
    if not backup_dir.exists():
        logger.error("❌ storage_backup 目录不存在")
        return False
    
    avatar_dir = backup_dir / "avatars"
    result_dir = backup_dir / "reports" / "Result_image"
    
    if not avatar_dir.exists():
        logger.warning(f"⚠️  头像目录不存在: {avatar_dir}")
    else:
        avatar_files = list(avatar_dir.glob("*"))
        logger.info(f"📁 找到 {len(avatar_files)} 个头像文件")
    
    if not result_dir.exists():
        logger.warning(f"⚠️  结果图片目录不存在: {result_dir}")
    else:
        result_files = list(result_dir.glob("*"))
        logger.info(f"📁 找到 {len(result_files)} 个结果图片文件")
    
    # 检查迁移脚本
    migration_dir = Path("migration")
    if not migration_dir.exists():
        logger.error("❌ migration 目录不存在")
        return False
    
    required_scripts = [
        "create_avatar_result_tables.py",
        "migrate_files_to_db.py"
    ]
    
    for script in required_scripts:
        script_path = migration_dir / script
        if not script_path.exists():
            logger.error(f"❌ 迁移脚本不存在: {script_path}")
            return False
    
    logger.info("✅ 前提条件检查通过")
    return True

def main():
    """主函数"""
    logger.info("🎯 开始头像和结果图片数据库迁移")
    logger.info("=" * 60)
    
    # 检查前提条件
    if not check_prerequisites():
        logger.error("❌ 前提条件检查失败，迁移终止")
        sys.exit(1)
    
    # 步骤1: 创建数据库表
    logger.info("📋 步骤 1/2: 创建数据库表")
    if not run_script("migration/create_avatar_result_tables.py", "创建数据库表"):
        logger.error("❌ 数据库表创建失败，迁移终止")
        sys.exit(1)
    
    # 步骤2: 迁移文件数据
    logger.info("📋 步骤 2/2: 迁移文件数据")
    if not run_script("migration/migrate_files_to_db.py", "迁移文件数据"):
        logger.error("❌ 文件数据迁移失败")
        sys.exit(1)
    
    # 迁移完成
    logger.info("=" * 60)
    logger.info("🎉 头像和结果图片迁移完成！")
    logger.info("")
    logger.info("📊 迁移摘要:")
    logger.info("  ✅ 创建了 avatars 表用于存储用户头像")
    logger.info("  ✅ 创建了 result_imgs 表用于存储检测结果图片")
    logger.info("  ✅ 修改了 dense_image 表以支持结果图片关联")
    logger.info("  ✅ 将文件数据成功导入到数据库")
    logger.info("")
    logger.info("🔧 后续步骤:")
    logger.info("  1. 更新应用代码以使用新的数据库表")
    logger.info("  2. 测试头像和结果图片的显示功能")
    logger.info("  3. 确认迁移成功后可以删除 storage_backup 目录")

if __name__ == "__main__":
    main()