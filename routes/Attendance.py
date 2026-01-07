
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from starlette.responses import JSONResponse
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from config.configrations import attendance_collection, users_collection, account_collection, class_collection, matkul_collection
from models.Account import Account
from models.Users import UserModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

SECRET_KEY = "your_secret_key"  # Use the same as in Account router
ALGORITHM = "HS256"

router = APIRouter()

# JWT dependency (reuse from Account router if possible)
bearer_scheme = HTTPBearer()
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
        # Get full account info
        acc = account_collection.find_one({"_id": ObjectId(account_id)})
        if not acc:
            raise credentials_exception
        acc["id"] = str(acc["_id"])
        return acc
    except Exception:
        raise credentials_exception

# --- Attendance Report Endpoint ---

# --- Scenario A: By Schedule (auto) ---

@router.get("/attendance/report/by-schedule")
async def attendance_report_by_schedule(
    course_name: str = Query(..., description="Nama mata kuliah (course name)"),
    meeting_date: str = Query(..., description="Tanggal pertemuan (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user)
):
    # Query jadwal berdasarkan nama_matkul dan dosen_id
    jadwal = matkul_collection.find_one({
        "nama_matkul": course_name,
        "account_id": ObjectId(current_user["id"])
    })
    
    print(f"[DEBUG] Retrieved jadwal for course '{course_name}': {jadwal}")
    
    # if not jadwal:
    #     raise HTTPException(
    #         status_code=404, 
    #         detail=f"Course '{course_name}' not found in lecturer's schedule YAYA"
    #     )
    
    # Validasi field yang diperlukan
    if not jadwal.get("jam_awal") or not jadwal.get("jam_akhir"):
        raise HTTPException(
            status_code=400, 
            detail="Schedule is incomplete (missing jam_awal or jam_akhir)"
        )
    
    # Ambil data waktu dan class_id
    waktu_mulai = jadwal["jam_awal"]
    waktu_selesai = jadwal["jam_akhir"]
    
    # Gunakan _id dari jadwal sebagai class_id (atau sesuaikan dengan struktur Anda)
    # Jika Anda punya field class_id di jadwal, gunakan itu
    class_id = jadwal.get("class_id") or jadwal["_id"]
    
    # Convert ke ObjectId jika belum
    if isinstance(class_id, str):
        try:
            class_obj_id = ObjectId(class_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid class_id format")
    else:
        class_obj_id = class_id
    print(f"[DEBUG] Retrieved schedule: course_name={course_name}, meeting_date={meeting_date}, waktu_mulai={waktu_mulai}, waktu_selesai={waktu_selesai}, class_id={class_id}")
    if not class_collection.find_one({"_id": class_obj_id}):
        raise HTTPException(status_code=404, detail="Class not found")
    try:
        start_time = datetime.strptime(f"{meeting_date} {waktu_mulai}", "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(f"{meeting_date} {waktu_selesai}", "%Y-%m-%d %H:%M")
        
        # Adjustment for WIB to UTC
        start_time = start_time - timedelta(hours=7)
        end_time = end_time - timedelta(hours=7)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time: {e}")
    print(f"[DEBUG] BY SCHEDULE: course_name={course_name}, meeting_date={meeting_date}, start_time={start_time}, end_time={end_time}, class_id={class_id}")
    pipeline = [
        {"$addFields": {
            "timestamp_date": {"$toDate": "$timestamp"}
        }},
        {"$match": {
            "timestamp_date": {"$gte": start_time, "$lte": end_time},
            "$or": [
                {"class_id": str(class_obj_id)},
                {"class_id": class_obj_id}
            ]
        }},
        {"$lookup": {
            "from": "Users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "student_info"
        }},
        {"$lookup": {
            "from": "Visitors",
            "localField": "visitor_id",
            "foreignField": "_id",
            "as": "visitor_info"
        }},
        {"$project": {
            "timestamp": 1,
            "full_name": {
                "$cond": [
                    {"$gt": [{"$size": "$student_info"}, 0]},
                    {"$arrayElemAt": ["$student_info.name", 0]},
                    {"$arrayElemAt": ["$visitor_info.name", 0]}
                ]
            },
            "category": {
                "$cond": [
                    {"$gt": [{"$size": "$student_info"}, 0]},
                    "Mahasiswa",
                    "Visitor"
                ]
            }
        }}
    ]
    results = list(attendance_collection.aggregate(pipeline))
    print(f"[DEBUG] Matched attendance records: {len(results)}")
    if results:
        print(f"[DEBUG] First result: {results[0]}")
    print(f"[DEBUG] Attendees: {[r.get('full_name', 'Unknown') for r in results]}")
    for r in results:
        # Convert ObjectId fields to string
        for k, v in r.items():
            if isinstance(v, ObjectId):
                r[k] = str(v)
        if isinstance(r.get("timestamp"), datetime):
            r["timestamp"] = r["timestamp"].isoformat()
        # Ensure full_name and category exist
        if 'full_name' not in r:
            r['full_name'] = 'Unknown'
        if 'category' not in r:
            r['category'] = 'Unknown'
    return {
        "scenario": "by-schedule",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "total_attendance": len(results),
        "attendees": results
    }

# --- Scenario B: Manual (custom time range) ---

@router.get("/attendance/report/by-manual")
async def attendance_report_by_manual(
    class_id: str = Query(..., description="ID kelas (class_id)"),
    specific_date: str = Query(..., description="Tanggal (YYYY-MM-DD)"),
    start_time_str: str = Query(..., description="Jam mulai (HH:mm)"),
    end_time_str: str = Query(..., description="Jam selesai (HH:mm)"),
    # current_user: dict = Depends(get_current_user)
):
    try:
        start_time = datetime.strptime(f"{specific_date} {start_time_str}", "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(f"{specific_date} {end_time_str}", "%Y-%m-%d %H:%M")
        
        # Adjustment for WIB to UTC
        start_time = start_time - timedelta(hours=7)
        end_time = end_time - timedelta(hours=7)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time: {e}")
    # Validate class_id is a valid ObjectId format and exists in Class collection
    try:
        class_obj_id = ObjectId(class_id)
    except Exception:
        raise HTTPException(status_code=400, detail="class_id is not a valid ObjectId")
    if not class_collection.find_one({"_id": class_obj_id}):
        raise HTTPException(status_code=404, detail="Class not found")
    print(f"[DEBUG] BY MANUAL: class_id={class_id}, specific_date={specific_date}, start_time={start_time}, end_time={end_time}")
    
    # Check if class_id in attendance is stored as string or ObjectId
    # Try to match both string and ObjectId format
    pipeline = [
        {"$addFields": {
            "timestamp_date": {"$toDate": "$timestamp"}
        }},
        {"$match": {
            "timestamp_date": {"$gte": start_time, "$lte": end_time},
            "$or": [
                {"class_id": class_id},  # Match as string
                {"class_id": class_obj_id}  # Match as ObjectId
            ]
        }},
        {"$lookup": {
            "from": "Users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "student_info"
        }},
        {"$lookup": {
            "from": "Visitors",
            "localField": "visitor_id",
            "foreignField": "_id",
            "as": "visitor_info"
        }},
        {"$project": {
            "timestamp": 1,
            "full_name": {
                "$cond": [
                    {"$gt": [{"$size": "$student_info"}, 0]},
                    {"$arrayElemAt": ["$student_info.name", 0]},
                    {"$arrayElemAt": ["$visitor_info.name", 0]}
                ]
            },
            "category": {
                "$cond": [
                    {"$gt": [{"$size": "$student_info"}, 0]},
                    "Mahasiswa",
                    "Visitor"
                ]
            }
        }}
    ]
    results = list(attendance_collection.aggregate(pipeline))
    print(f"[DEBUG] Matched attendance records: {len(results)}")
    if results:
        print(f"[DEBUG] First result: {results[0]}")
    print(f"[DEBUG] Attendees: {[r.get('full_name', 'Unknown') for r in results]}")
    for r in results:
        # Convert ObjectId fields to string
        for k, v in r.items():
            if isinstance(v, ObjectId):
                r[k] = str(v)
        if isinstance(r.get("timestamp"), datetime):
            r["timestamp"] = r["timestamp"].isoformat()
        # Ensure full_name and category exist
        if 'full_name' not in r:
            r['full_name'] = 'Unknown'
        if 'category' not in r:
            r['category'] = 'Unknown'
    return {
        "scenario": "by-manual",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "total_attendance": len(results),
        "attendees": results
    }

# --- Bulk Attendance Update Endpoint ---

class AttendanceUpdateItem(BaseModel):
    user_id: str
    present: bool
    waktu_absen: Optional[str] = None

class UpdateAttendanceRequest(BaseModel):
    matkul_id: str
    pertemuan: int
    attendance: List[AttendanceUpdateItem]

@router.post("/update-bulk")
async def update_attendance_bulk(
    request: UpdateAttendanceRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Bulk update attendance records for a specific meeting.
    - If present=True and record doesn't exist: INSERT new attendance
    - If present=True and record exists: UPDATE timestamp if changed
    - If present=False and record exists: DELETE attendance record
    """
    from datetime import timedelta
    
    try:
        matkul_obj_id = ObjectId(request.matkul_id)
        account_id = ObjectId(current_user["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    
    # Verify matkul belongs to current user
    matkul = matkul_collection.find_one({"_id": matkul_obj_id, "account_id": account_id})
    if not matkul:
        raise HTTPException(status_code=404, detail="Matkul not found or not authorized")
    
    # Get matkul details
    tanggal_awal = matkul.get("tanggal_awal")
    jam_awal = matkul.get("jam_awal")
    class_id = matkul.get("class_id")
    
    if not tanggal_awal:
        raise HTTPException(status_code=400, detail="Matkul is missing tanggal_awal")
    
    # Parse tanggal_awal
    if isinstance(tanggal_awal, str):
        try:
            tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tanggal_awal format")
    
    # Calculate meeting date
    if isinstance(tanggal_awal, datetime):
        start_date = tanggal_awal.date()
    else:
        start_date = tanggal_awal
    
    pertemuan_date = start_date + timedelta(weeks=request.pertemuan - 1)
    meeting_date_str = pertemuan_date.strftime("%Y-%m-%d")
    
    # Process each student's attendance
    inserted_count = 0
    updated_count = 0
    deleted_count = 0
    
    for item in request.attendance:
        try:
            user_obj_id = ObjectId(item.user_id)
        except Exception:
            continue  # Skip invalid user IDs
        
        # Build query to find existing attendance record
        # Match by user_id and class_id, with timestamp within the meeting date
        if jam_awal:
            start_time = datetime.strptime(f"{meeting_date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(f"{meeting_date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
        else:
            start_time = datetime.strptime(f"{meeting_date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(f"{meeting_date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
        
        # Build class ID matching conditions
        class_match = []
        if class_id:
            class_match.append({"class_id": class_id})
            class_match.append({"class_id": str(class_id)})
            if isinstance(class_id, str):
                try:
                    class_match.append({"class_id": ObjectId(class_id)})
                except:
                    pass
        
        # Find existing attendance records for this user and class
        # Use simple find instead of aggregation to avoid $toDate errors on corrupted data
        find_query = {
            "user_id": user_obj_id,
        }
        if class_match:
            find_query["$or"] = class_match
        
        existing_records = list(attendance_collection.find(find_query))
        
        # Filter by date in Python (safer than MongoDB $toDate on potentially corrupt data)
        existing = None
        for record in existing_records:
            ts = record.get("timestamp", "")
            if isinstance(ts, str) and meeting_date_str in ts:
                existing = record
                break
            elif isinstance(ts, datetime):
                if ts.date() == pertemuan_date:
                    existing = record
                    break
        
        if item.present:
            # Handle waktu_absen - could be full ISO timestamp or just time
            if item.waktu_absen:
                waktu = item.waktu_absen.strip()
                # Check if it's already a full ISO timestamp (contains 'T' and looks like a date)
                if 'T' in waktu and len(waktu) > 10:
                    # Already a full timestamp, use it directly
                    # Remove trailing 'Z' if present and add it back consistently
                    timestamp_iso = waktu.rstrip('Z') + 'Z' if waktu.endswith('Z') else waktu
                    # Validate it's a proper timestamp
                    try:
                        datetime.fromisoformat(waktu.replace('Z', '+00:00'))
                        timestamp_iso = waktu
                    except:
                        # If invalid, construct from meeting date
                        timestamp_iso = f"{meeting_date_str}T{jam_awal}:00Z" if jam_awal else f"{meeting_date_str}T08:00:00Z"
                else:
                    # Just time component (HH:MM:SS or HH:MM), combine with meeting date
                    timestamp_iso = f"{meeting_date_str}T{waktu}Z"
            else:
                # Default to start of class time
                timestamp_iso = f"{meeting_date_str}T{jam_awal}:00Z" if jam_awal else f"{meeting_date_str}T08:00:00Z"
            
            if existing:
                # Update existing record
                attendance_collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"timestamp": timestamp_iso}}
                )
                updated_count += 1
            else:
                # Insert new record
                new_record = {
                    "user_id": user_obj_id,
                    "class_id": class_id if class_id else matkul_obj_id,
                    "timestamp": timestamp_iso
                }
                attendance_collection.insert_one(new_record)
                inserted_count += 1
        else:
            # Delete record if exists
            if existing:
                attendance_collection.delete_one({"_id": existing["_id"]})
                deleted_count += 1
    
    return {
        "message": "Attendance updated successfully",
        "inserted": inserted_count,
        "updated": updated_count,
        "deleted": deleted_count
    }