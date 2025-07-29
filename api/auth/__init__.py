"""
Authentication and Session Management API

This module provides enhanced authentication and session management functionality.
"""

from fastapi import APIRouter
from .session import router as session_router
from .auth import router as auth_router
from .password_reset import router as password_reset_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(session_router)
router.include_router(password_reset_router)