from fastapi import APIRouter
from fastapi.requests import Request
from starlette.responses import StreamingResponse

from database.api import uploadImage
from utils.request import TokenRequest
from utils.response import Response
from utils import resolveAccountJwt
from database.storage import load_image

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
        return StreamingResponse(open("default.png", "rb"))
    return StreamingResponse([image_data])
