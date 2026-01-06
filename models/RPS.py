from pydantic import BaseModel, Field
from typing import Optional

class RPSModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # Student ID
    matkul_id: str  # Course ID

    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "user_id": "695b8c2b540a02b5137daea6",
                "matkul_id": "695b8b477afa3aa72dc31445"
            }
        }