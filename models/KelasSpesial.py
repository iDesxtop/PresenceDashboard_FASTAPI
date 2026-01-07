from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class KelasSpesialModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    matkul_id: str
    class_id: Optional[str] = None  # Nullable for online classes
    pertemuan: int
    jam_awal: str
    jam_akhir: str
    tanggal_kelas: datetime
    is_online: bool = False

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "matkul_id": "695bd0e37563f8ba7000a9a5",
                "class_id": "694f3f1b825e7bcbbe801d14",
                "pertemuan": 16,
                "jam_awal": "10:00",
                "jam_akhir": "12:15",
                "tanggal_kelas": "2026-04-21T10:00:00.000Z",
                "is_online": False
            }
        }

class RescheduleRequest(BaseModel):
    matkul_id: str
    pertemuan: int
    tanggal_baru: str # YYYY-MM-DD
    jam_mulai_baru: str # HH:MM
    jam_selesai_baru: str # HH:MM
    class_id: Optional[str] = None
    is_online: bool = False
