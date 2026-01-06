from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse
from typing import List
from config.configrations import db
from bson import ObjectId
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your_secret_key"  # Use the same as in Account router
ALGORITHM = "HS256"

router = APIRouter()
bearer_scheme = HTTPBearer()

# Get collections
rps_collection = db["RPS"]
users_collection = db["Users"]
matkul_collection = db["Matkul"]
attendance_collection = db["Attendance"]

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_id: str = payload.get("account_id")
        jabatan: str = payload.get("jabatan")
        if account_id is None or jabatan is None:
            raise credentials_exception
        return {"account_id": account_id, "jabatan": jabatan}
    except Exception:
        raise credentials_exception

def normalize_doc(doc: dict):
    """Convert ObjectId and datetime to string for JSON serialization"""
    if not doc:
        return doc
    d = dict(doc)
    
    # Convert ObjectId to string for _id
    _id = d.get("_id")
    if _id is not None:
        try:
            d["_id"] = str(_id)
        except Exception:
            d["_id"] = _id
    
    # Convert ObjectId and datetime fields to strings
    for key, value in d.items():
        if isinstance(value, ObjectId):
            d[key] = str(value)
        elif isinstance(value, datetime):
            d[key] = value.isoformat()
    
    return d

@router.get("/matkul/{matkul_id}/students", tags=["RPS"])
async def get_enrolled_students(matkul_id: str, current_user: dict = Depends(get_current_user)):
    """Get all students enrolled in a specific Matkul"""
    try:
        matkul_obj_id = ObjectId(matkul_id)
        account_id = ObjectId(current_user["account_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    
    # Verify that the current user teaches this Matkul
    matkul = matkul_collection.find_one({
        "_id": matkul_obj_id,
        "account_id": account_id
    })
    
    if not matkul:
        raise HTTPException(status_code=404, detail="Matkul not found or not authorized")
    
    # Get all RPS records for this Matkul
    rps_records = list(rps_collection.find({"matkul_id": matkul_obj_id}))
    
    # Get student details
    enrolled_students = []
    for rps in rps_records:
        try:
            user_obj_id = ObjectId(rps["user_id"])
            student = users_collection.find_one({"_id": user_obj_id})
            if student:
                student_normalized = normalize_doc(student)
                enrolled_students.append(student_normalized)
        except Exception:
            continue
    
    return JSONResponse(content={
        "matkul_id": matkul_id,
        "total_enrolled": len(enrolled_students),
        "students": enrolled_students
    })

@router.get("/matkul/{matkul_id}/attendance-summary", tags=["RPS"])
async def get_attendance_summary_by_pertemuan(matkul_id: str, current_user: dict = Depends(get_current_user)):
    """Get attendance summary for each Pertemuan in a Matkul"""
    try:
        matkul_obj_id = ObjectId(matkul_id)
        account_id = ObjectId(current_user["account_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    
    # Verify that the current user teaches this Matkul
    matkul = matkul_collection.find_one({
        "_id": matkul_obj_id,
        "account_id": account_id
    })
    
    if not matkul:
        raise HTTPException(status_code=404, detail="Matkul not found or not authorized")
    
    # Get total enrolled students
    total_enrolled = rps_collection.count_documents({"matkul_id": matkul_obj_id})
    
    # Calculate Pertemuan dates (same logic as in Matkul.py)
    tanggal_awal = matkul.get("tanggal_awal")
    if isinstance(tanggal_awal, str):
        tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
    
    if isinstance(tanggal_awal, datetime):
        start_date = tanggal_awal.date()
    else:
        start_date = tanggal_awal
    
    pertemuan_attendance = []
    
    for i in range(1, 17):  # Pertemuan 1 to 16
        # Calculate the date for this pertemuan (weekly intervals)
        pertemuan_date = start_date + timedelta(weeks=i-1)
        
        # Get attendance count for this specific date
        # Attendance records should have the class_id from the Matkul
        class_id = matkul.get("class_id")
        
        if class_id:
            # Count attendance for this specific date and class
            start_datetime = datetime.combine(pertemuan_date, datetime.min.time())
            end_datetime = datetime.combine(pertemuan_date, datetime.max.time())
            
            attendance_count = attendance_collection.count_documents({
                "class_id": class_id,
                "timestamp": {
                    "$gte": start_datetime,
                    "$lte": end_datetime
                }
            })
        else:
            attendance_count = 0
        
        pertemuan_attendance.append({
            "pertemuan": i,
            "tanggal": pertemuan_date.isoformat(),
            "present_count": attendance_count,
            "total_enrolled": total_enrolled,
            "attendance_ratio": f"{attendance_count}/{total_enrolled}"
        })
    
    return JSONResponse(content={
        "matkul_id": matkul_id,
        "total_enrolled": total_enrolled,
        "pertemuan_attendance": pertemuan_attendance
    })