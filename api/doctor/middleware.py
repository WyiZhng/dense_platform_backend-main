"""
Doctor API Middleware

This module provides middleware for doctor API endpoints to handle token extraction
from headers and automatic injection into request bodies.
"""

from typing import Callable, Dict, Any
from fastapi import Request, Response
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class DoctorTokenMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract token from Authorization header and inject it into request body
    for doctor API endpoints that require TokenRequest.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request before passing it to the endpoint
        
        Args:
            request: The incoming request
            call_next: The next middleware or endpoint
            
        Returns:
            The response from the endpoint
        """
        # Only process POST requests to doctor API endpoints
        if request.method == "POST" and "/api/doctor/" in request.url.path:
            # Try to get token from Authorization header
            auth_header = request.headers.get("Authorization")
            token = None
            
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
            
            # If token found, modify request body to include it
            if token:
                try:
                    # Read and parse request body
                    body = await request.body()
                    if body:
                        body_dict = json.loads(body)
                    else:
                        body_dict = {}
                    
                    # Add token if not already present
                    if "token" not in body_dict:
                        body_dict["token"] = token
                    
                    # Create a modified request with the updated body
                    async def receive():
                        return {
                            "type": "http.request",
                            "body": json.dumps(body_dict).encode(),
                            "more_body": False
                        }
                    
                    # Override the receive method to return our modified body
                    request._receive = receive
                except Exception as e:
                    print(f"Error in DoctorTokenMiddleware: {e}")
                    # Continue with original request if there's an error
        
        # Process the request with the next middleware or endpoint
        response = await call_next(request)
        return response