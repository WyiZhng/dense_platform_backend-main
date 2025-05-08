import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api import router

app = FastAPI()
origins = [

    "http://localhost",
    "http://localhost:5173",
    "http://192.168.71.86:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
def handle_all(request: Request, ex: Exception):
    return {"code": -1, "message": ex}
