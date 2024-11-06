from pydantic import BaseModel, Field, HttpUrl, AnyUrl
from typing import Optional, List, Dict, Any
from uuid import uuid4

class GoogleMapsLead(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    business_phone: Optional[str] = None
    formatted_address: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    types: Optional[List[str]] = None
    business_status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    additional_properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    images: Optional[List[str]] = None
    reviews: Optional[List[Dict[str, Any]]] = None
    similar_businesses: Optional[List[Dict[str, Any]]] = None
    about: Optional[str] = None

    class Config:
        json_encoders = {
            AnyUrl: str
        }
