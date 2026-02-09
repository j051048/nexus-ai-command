"""
P2 Security: Security Headers Middleware

Adds security headers to all responses to prevent common web vulnerabilities:
- XSS (Cross-Site Scripting)
- Clickjacking
- MIME type sniffing
- Information disclosure
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.
    
    These headers help protect against various web vulnerabilities
    and are recommended by OWASP security guidelines.
    """
    
    # Default security headers
    SECURITY_HEADERS = {
        # Prevent XSS attacks
        "X-Content-Type-Options": "nosniff",
        
        # Prevent clickjacking
        "X-Frame-Options": "DENY",
        
        # Enable XSS filter in browsers
        "X-XSS-Protection": "1; mode=block",
        
        # Referrer policy for privacy
        "Referrer-Policy": "strict-origin-when-cross-origin",
        
        # Prevent MIME type sniffing  
        "Content-Type-Options": "nosniff",
        
        # Cache control for sensitive data
        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
        "Pragma": "no-cache",
        
        # Permissions policy (restrict browser features)
        "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
    }
    
    # Paths that may need different caching
    STATIC_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Add security headers to all responses
        for header_name, header_value in self.SECURITY_HEADERS.items():
            # Don't override if already set
            if header_name not in response.headers:
                response.headers[header_name] = header_value
        
        # Allow caching for static/documentation paths
        if request.url.path in self.STATIC_PATHS:
            response.headers["Cache-Control"] = "public, max-age=3600"
        
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request.
    
    Useful for tracing requests across logs and services.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        import uuid
        
        # Check if request ID already provided (e.g., from load balancer)
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in request state for access in route handlers
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
