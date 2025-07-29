from fastapi import APIRouter, Depends
from fastapi.requests import Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.database.storage import load_image, load_result_image, load_avatars_image
from dense_platform_backend_main.services.rbac_middleware import RequireAuthWithContext
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.api.auth.session import get_db
router = APIRouter()
class ImageResponse(Response):
    image: str


@router.post("/api/image")
async def image(
    request: Request,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """上传图片 - 需要认证 (使用数据库存储)"""
    try:
        username = current_user["user_id"]
        print(f"DEBUG: 用户 {username} 开始上传图片")
        
        form = await request.form()
        file = form.get("file")
        
        if not file:
            print("DEBUG: 没有找到上传的文件")
            return Response(code=400, message="没有找到上传的文件")
        
        print(f"DEBUG: 上传文件信息 - 文件名: {file.filename}, 大小: {file.size if hasattr(file, 'size') else 'unknown'}")
        
        # 使用数据库存储服务
        file_data = await file.read()
        print(f"DEBUG: 读取文件数据，大小: {len(file_data)} bytes")
        
        file_format = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'jpg'
        print(f"DEBUG: 文件格式: {file_format}")
        
        image_id = DatabaseStorageService.save_image(db, file_data, file.filename or "uploaded_image", file_format)
        print(f"DEBUG: 保存图片结果，ID: {image_id}")
        
        if image_id:
            return ImageResponse(image=image_id)
        else:
            return Response(code=500, message="图片保存失败")
            
    except Exception as e:
        print(f"ERROR: 图片上传异常: {e}")
        import traceback
        traceback.print_exc()
        return Response(code=500, message=f"图片上传失败: {str(e)}")


class GetImageRequest(BaseModel):
    id: str


@router.post("/api/image/get")
async def getImage(
    request: GetImageRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """获取图片 - 需要认证 (使用数据库存储)"""
    username = current_user["user_id"]
    
    # 使用数据库存储服务
    image_data = DatabaseStorageService.load_image(db, request.id)
    
    if not image_data:
        # 如果数据库中没有找到，尝试从文件系统加载（向后兼容）
        image_data = load_image(request.id)
        if not image_data:
            image_data = load_result_image(request.id)
            if not image_data:
                image_data = load_avatars_image(request.id)
                if not image_data:
                    # 返回默认图片或404
                    from fastapi import HTTPException
                    raise HTTPException(status_code=404, detail="Image not found")
    
    # 正确使用StreamingResponse
    import io
    return StreamingResponse(
        io.BytesIO(image_data), 
        media_type="image/jpeg",
        headers={"Content-Disposition": "inline"}
    )


@router.post("/api/image/getresult_img")
async def getResultImage(
    request: GetImageRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """获取结果图片 - 需要认证 (从result_imgs表获取)"""
    username = current_user["user_id"]
    
    # 使用数据库存储服务获取结果图片
    image_data = DatabaseStorageService.load_result_image(db, request.id)
    
    if not image_data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Result image not found")
    
    # 正确使用StreamingResponse
    import io
    return StreamingResponse(
        io.BytesIO(image_data), 
        media_type="image/jpeg",
        headers={"Content-Disposition": "inline"}
    )

