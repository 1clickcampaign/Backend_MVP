from pydantic import BaseModel, UUID4, constr
from typing import Optional
from datetime import datetime

# Base list model shared between requests and responses
class ListBase(BaseModel):
    name: constr(min_length=1)
    description: Optional[str]

# Model for list creation input
class ListCreate(ListBase):
    pass

# Model for list response with ID and timestamps
class ListResponse(ListBase):
    id: UUID4
    user_id: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Model for updating a list
class ListUpdate(BaseModel):
    name: Optional[constr(min_length=1)]
    description: Optional[str]

    class Config:
        orm_mode = True
