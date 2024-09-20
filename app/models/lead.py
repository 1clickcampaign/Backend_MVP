from pydantic import BaseModel, Field, HttpUrl, constr, conlist, UUID4
from typing import Optional, List, Dict
from datetime import datetime

# Pydantic model for lead input and output
class LeadBase(BaseModel):
    name: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    external_id: str = Field(..., min_length=1) 
    business_phone: Optional[str]
    business_email: Optional[str]
    decision_maker_name: Optional[str]
    decision_maker_linkedin: Optional[HttpUrl]
    decision_maker_email: Optional[str]
    decision_maker_phone: Optional[str]

    # This field will store the source-specific attributes in JSONB
    source_attributes: Optional[Dict[str, str]]

    class Config:
        orm_mode = True  # Allows the model to work seamlessly with SQLAlchemy

# Model for lead creation input
class LeadCreate(LeadBase):
    pass

# Model for lead response with timestamps
class LeadResponse(LeadBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

# Model for updating leads
class LeadUpdate(BaseModel):
    business_phone: Optional[str]
    business_email: Optional[str]
    decision_maker_name: Optional[str]
    decision_maker_linkedin: Optional[HttpUrl]
    decision_maker_email: Optional[str]
    decision_maker_phone: Optional[str]
    source_attributes: Optional[Dict[str, str]]

    class Config:
        orm_mode = True
