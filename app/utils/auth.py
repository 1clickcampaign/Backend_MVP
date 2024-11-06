"""
Auth Utils
"""

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
import os
import logging
from .database import SupabaseClientSingleton

# Configure logging
logger = logging.getLogger(__name__)

# Environment variables
jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")
if not jwt_secret:
    raise ValueError("SUPABASE_JWT_SECRET is not set in environment variables")

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify and decode the JWT token from Supabase.
    
    Args:
        credentials (HTTPAuthorizationCredentials): The credentials containing the JWT token.
        
    Returns:
        str: The user ID from the token.
        
    Raises:
        HTTPException: If the token is invalid, expired, or missing required claims.
    """
    token = credentials.credentials
    try:
        # Get Supabase client instance
        supabase = SupabaseClientSingleton.get_instance()
        
        # Decode the JWT token with the Supabase JWT secret
        payload = jwt.decode(
            token, 
            jwt_secret, 
            algorithms=["HS256"],
            audience="authenticated"
        )
        
        # Extract user ID from the token
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token: missing user ID"
            )
            
        # Verify user exists in Supabase
        response = supabase.table("users").select("id").eq("id", user_id).execute()
        if not response.data:
            logger.warning(f"User {user_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
            
        return user_id
        
    except jwt.ExpiredSignatureError:
        logger.warning(f"Token expired: {token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {token}, Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Unexpected error in token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing authentication token"
        )

def verify_api_key(request: Request) -> str:
    """
    Verify the API key from the request headers.
    
    Args:
        request (Request): The FastAPI request object.
        
    Returns:
        str: The API key if valid.
        
    Raises:
        HTTPException: If the API key is invalid or missing.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != os.environ.get("API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return api_key
