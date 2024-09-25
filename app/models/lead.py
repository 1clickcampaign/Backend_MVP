from pydantic import BaseModel, Field, HttpUrl, constr, conlist, UUID4
from typing import Any, Optional, Dict
from datetime import datetime

# Pydantic model for lead input and output
class LeadBase(BaseModel):
    name: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    external_id: str = Field(..., min_length=1)
    business_phone: Optional[str] = None
    business_email: Optional[str] = None
    decision_maker_name: Optional[str] = None
    decision_maker_linkedin: Optional[HttpUrl] = None
    decision_maker_email: Optional[str] = None
    decision_maker_phone: Optional[str] = None

    # This field will store the source-specific attributes in JSONB
    source_attributes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# Model for lead creation input
class LeadCreate(BaseModel):
    name: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    external_id: str = Field(..., min_length=1)
    business_phone: Optional[str] = None
    business_email: Optional[str] = None
    decision_maker_name: Optional[str] = None
    decision_maker_linkedin: Optional[HttpUrl] = None
    decision_maker_email: Optional[str] = None
    decision_maker_phone: Optional[str] = None
    source_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # This allows extra fields that are not defined in the model

    def dict(self, *args, **kwargs):
        # Custom dict method to include extra fields
        d = super().dict(*args, **kwargs)
        d.update({k: v for k, v in self.__dict__.items() if k not in d})
        return d

# Model for lead response with timestamps
class LeadResponse(LeadBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

# Model for updating leads
class LeadUpdate(BaseModel):
    business_phone: Optional[str] = None
    business_email: Optional[str] = None
    decision_maker_name: Optional[str] = None
    decision_maker_linkedin: Optional[HttpUrl] = None
    decision_maker_email: Optional[str] = None
    decision_maker_phone: Optional[str] = None
    source_attributes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

