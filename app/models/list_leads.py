from pydantic import BaseModel, UUID4

# Base model for the relationship between lists and leads
class ListLeadBase(BaseModel):
    list_id: UUID4
    lead_id: UUID4

# Model for the response of list-lead relations
class ListLeadResponse(ListLeadBase):
    class Config:
        orm_mode = True
