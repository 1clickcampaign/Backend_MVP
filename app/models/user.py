from pydantic import BaseModel, EmailStr, UUID4, constr
from datetime import datetime
from typing import Optional

# Base user model shared between requests and responses
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str]

# Model for user creation input
class UserCreate(UserBase):
    password: constr(min_length=6)

# Model for user response with ID and timestamps
class UserResponse(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True  # Allows the model to work with SQLAlchemy

# Model for user update input
class UserUpdate(BaseModel):
    email: Optional[EmailStr]
    name: Optional[str]

    class Config:
        orm_mode = True
