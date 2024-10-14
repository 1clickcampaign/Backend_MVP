"""
Auth Utils
"""

from fastapi import HTTPException, status
from app.utils.config import API_KEY

def verify_api_key(api_key: str) -> bool:
    """
    Verify the API key.
    """
    if api_key is None or api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
