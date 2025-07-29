#!/usr/bin/env python3
"""
初始化默认头像到数据库

这个脚本将default.png文件加载到avatars表中，作为所有新用户的默认头像
"""

import os
import sys
sys.path.append('.')

from api.auth.session import get_db_session
from services.database_storage_service import DatabaseStorageService

def init_default_avatar():
    """初始化默认头像到数据库"""
    try:
        # 获取数据库会话
        db = get_db_session()
        
        # 检查默认头像是否已经存在
        existing_avatar = DatabaseStorageService.load_avatar(db, "default")
        if existing_avatar:
            print("✅ 默认头像已存在于数据库中")
            db.close()
            return True
        
        # 加载默认头像文件
        default_avatar_path = "default.png"
        if not os.path.exists(default_avatar_path):
            print(f"❌ 默认头像文件不存在: {default_avatar_path}")
            db.close()
            return False
        
        print(f"📁 加载默认头像文件: {default_avatar_path}")
        with open(default_avatar_path, "rb") as f:
            default_data = f.read()
        
        print(f"📊 默认头像文件大小: {len(default_data)} bytes")
        
        # 保存默认头像到数据库
        success = DatabaseStorageService.save_avatar(db, "default", default_data, "default.png")
        
        if success:
            print("✅ 默认头像已成功保存到数据库")
            
            # 验证保存是否成功
            saved_avatar = DatabaseStorageService.load_avatar(db, "default")
            if saved_avatar:
                print(f"✅ 验证成功: 默认头像大小 {len(saved_avatar)} bytes")
            else:
                print("❌ 验证失败: 无法从数据库加载默认头像")
                
        else:
            print("❌ 保存默认头像失败")
        
        db.close()
        return success
        
    except Exception as e:
        print(f"❌ 初始化默认头像时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始初始化默认头像...")
    success = init_default_avatar()
    if success:
        print("🎉 默认头像初始化完成！")
    else:
        print("💥 默认头像初始化失败！")
        sys.exit(1)