from pydantic import BaseModel, Field
from typing import Optional

class MatkulModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    nama_matkul: str
    sks: int
    dosen_id: str
    ruangan_id: Optional[str] = None
    hari: str
    jam_awal: str
    jam_akhir: str
    tanggal_awal: str

    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "nama_matkul": "System Cerdas",
                "sks": 3,
                "dosen_id": "60c72b2f9b1e8b3a2c8f9e7d",
                "ruangan_id": "60c72b2f9b1e8b3a2c8f9e7e",
                "hari": "Senin",
                "jam_awal": "07:00",
                "jam_akhir": "08:40",
                "tanggal_awal": "2026-01-06"
            }
        }