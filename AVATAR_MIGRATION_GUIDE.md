# 头像和结果图片数据库迁移指南

## 概述

此迁移将创建两个新的数据库表来存储头像和结果图片，并将现有的文件数据迁移到数据库中。

## 新增的数据库表

### 1. `avatars` 表
- 存储用户头像数据
- 字段：`id`, `user_id`, `filename`, `data`, `format`, `upload_time`, `file_size`
- 与 `user` 表建立外键关系

### 2. `result_imgs` 表  
- 存储报告检测结果图片
- 字段：`id`, `report_id`, `filename`, `data`, `format`, `created_time`, `file_size`
- 与 `dense_report` 表建立外键关系

### 3. 修改 `dense_image` 表
- 新增 `result_image` 字段，关联到 `result_imgs` 表
- 支持同时关联用户上传图片和检测结果图片

## 迁移步骤

### 准备工作

1. **确保备份目录存在**：
   ```
   storage_backup/
   ├── avatars/           # 用户头像文件
   └── reports/
       └── Result_image/  # 检测结果图片
   ```

2. **检查文件命名规范**：
   - 头像文件：`{user_id}.{ext}` 或 `{user_id}_avatar.{ext}`
   - 结果图片：`{report_id}.{ext}` 或 `{report_id}_result.{ext}`

### 执行迁移

运行主迁移脚本：

```bash
cd dense_platform_backend_main
python run_avatar_migration.py
```

### 迁移过程

1. **步骤 1/2：创建数据库表**
   - 创建 `avatars` 表
   - 创建 `result_imgs` 表
   - 修改 `dense_image` 表添加 `result_image` 字段

2. **步骤 2/2：迁移文件数据**
   - 将头像文件导入到 `avatars` 表
   - 将结果图片导入到 `result_imgs` 表
   - 更新 `dense_image` 表的关联关系

## 验证迁移结果

迁移完成后，系统会自动验证：

- ✅ 数据库表创建成功
- ✅ 文件数据正确导入
- ✅ 关联关系建立正确

## 新增的 API 功能

### DatabaseStorageService 新方法

#### 头像管理
- `save_avatar()` - 保存用户头像
- `load_avatar()` - 加载用户头像
- `get_avatar_info()` - 获取头像信息
- `delete_avatar()` - 删除用户头像

#### 结果图片管理
- `save_result_image()` - 保存结果图片
- `load_result_image()` - 加载结果图片
- `get_report_result_images()` - 获取报告的所有结果图片
- `delete_result_image()` - 删除结果图片

## 使用示例

### 保存用户头像
```python
from services.database_storage_service import DatabaseStorageService

# 保存头像
avatar_id = DatabaseStorageService.save_avatar(
    db=db_session,
    user_id="user123",
    avatar_data=image_bytes,
    filename="avatar.jpg",
    format="jpg"
)
```

### 获取用户头像
```python
# 加载头像数据
avatar_data = DatabaseStorageService.load_avatar(db_session, "user123")

# 获取头像信息
avatar_info = DatabaseStorageService.get_avatar_info(db_session, "user123")
```

### 保存结果图片
```python
# 保存结果图片
result_id = DatabaseStorageService.save_result_image(
    db=db_session,
    report_id="8",
    image_data=result_bytes,
    filename="result.jpg",
    format="jpg"
)
```

### 获取报告结果图片
```python
# 获取报告的所有结果图片
result_images = DatabaseStorageService.get_report_result_images(db_session, "8")
```

## 注意事项

1. **备份数据**：迁移前请备份数据库
2. **文件权限**：确保应用有读取 `storage_backup` 目录的权限
3. **磁盘空间**：确保数据库有足够空间存储图片数据
4. **性能考虑**：大量图片可能影响数据库性能，建议分批迁移

## 故障排除

### 常见问题

1. **目录不存在**
   ```
   ❌ storage_backup 目录不存在
   ```
   **解决方案**：创建相应目录并放置文件

2. **用户/报告不存在**
   ```
   ⚠️ 用户 xxx 不存在，跳过头像文件
   ```
   **解决方案**：检查文件命名是否正确

3. **权限不足**
   ```
   ❌ 权限不足，无法读取文件
   ```
   **解决方案**：检查文件权限设置

### 日志查看

迁移过程中的详细日志会显示：
- ✅ 成功操作
- ⚠️ 警告信息  
- ❌ 错误信息

## 迁移后清理

迁移成功后，可以考虑：

1. **删除备份文件**（确认迁移成功后）
2. **更新应用代码**以使用新的数据库存储
3. **测试头像和结果图片显示功能**

## 技术支持

如果遇到问题，请检查：
1. 数据库连接是否正常
2. 文件路径是否正确
3. 权限设置是否合适
4. 日志输出中的错误信息