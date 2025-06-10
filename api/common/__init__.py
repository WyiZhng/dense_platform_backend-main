from fastapi import APIRouter
from fastapi.requests import Request
from sqlalchemy.orm import sessionmaker
from starlette.responses import StreamingResponse

from dense_platform_backend_main.database.api import uploadImage
from dense_platform_backend_main.database.db import engine
from dense_platform_backend_main.database.table import Image
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import resolveAccountJwt
from dense_platform_backend_main.database.storage import load_image,load_result_image,load_avatars_image
router = APIRouter()

class ImageResponse(Response):
    image: str


@router.post("/api/image")
async def image(request: Request):
    form = await request.form()
    file = form.get("file")
    token = request.headers.get("token", default=None)
    if token is None:
        return Response(code=34, message="权限不足")
    username = resolveAccountJwt(token)['account']
    image_id = uploadImage(file.filename, await file.read())
    return ImageResponse(image=image_id)


class GetImageRequest(TokenRequest):
    id: str


@router.post("/api/image/get")
async def getImage(request: GetImageRequest):
    username = resolveAccountJwt(request.token)["account"]
    image_data = load_image(request.id)
    if not image_data:
        image_data = load_result_image(request.id)
        if not image_data:
            image_data = load_avatars_image(request.id)
            if not image_data:
                return StreamingResponse(open("default.png", "rb"))
    return StreamingResponse([image_data])


"""

class ImageResponse(Response):
    image: int


@router.post("/api/image")
async def image(request: Request):
    form = await request.form()
    file = form.get("file")
    token = request.headers.get("token", default=None)
    if token is None:
        return Response(code=34, message="权限不足")
    username = resolveAccountJwt(token)['account']
    session = sessionmaker(bind=engine)()
    with session:
        return ImageResponse(image=uploadImage(session, file.filename, await file.read()))


class GetImageRequest(TokenRequest):
    id: int


@router.post("/api/image/get")
async def getImage(request: GetImageRequest):
    username = resolveAccountJwt(request.token)["account"]
    session = sessionmaker(bind=engine)()
    with session:
        detail = session.query(Image).filter(Image.id == request.id).first()
        if not detail:
            return StreamingResponse(open("default.png", "rb"))
    return StreamingResponse([detail.data])
"""