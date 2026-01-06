from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse
from typing import List
from config.configrations import matkul_collection, class_collection, db, users_collection
from bson import ObjectId
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your_secret_key"  # Use the same as in Account router
ALGORITHM = "HS256"

router = APIRouter()
bearer_scheme = HTTPBearer()

# Get additional collections
rps_collection = db["RPS"]
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

def calculate_pertemuan_with_attendance(tanggal_awal, matkul_id, matkul_name, current_date=None):
    """Calculate the status of 16 Pertemuan with attendance data using the same logic as Attendance API"""
    if current_date is None:
        current_date = datetime.now().date()
    
    # Convert tanggal_awal to date if it's datetime
    if isinstance(tanggal_awal, datetime):
        start_date = tanggal_awal.date()
    else:
        start_date = tanggal_awal
    
    # Get total enrolled students for this Matkul
    try:
        matkul_obj_id = ObjectId(matkul_id)
        total_enrolled = rps_collection.count_documents({"matkul_id": matkul_obj_id})
    except Exception:
        total_enrolled = 0
    
    # Get the Matkul to find class_id and schedule info
    try:
        matkul = matkul_collection.find_one({"_id": matkul_obj_id})
        class_id = matkul.get("class_id") if matkul else None
        jam_awal = matkul.get("jam_awal") if matkul else None
        jam_akhir = matkul.get("jam_akhir") if matkul else None
    except Exception:
        class_id = None
        jam_awal = None
        jam_akhir = None
    
    pertemuan_list = []
    
    for i in range(1, 17):  # Pertemuan 1 to 16
        # Calculate the date for this pertemuan (weekly intervals)
        pertemuan_date = start_date + timedelta(weeks=i-1)
        
        # Determine status based on current date
        if pertemuan_date < current_date:
            status = "Selesai"
        elif pertemuan_date == current_date:
            status = "Sedang Berlangsung"
        else:
            status = "Belum Dimulai"
        
        # Get attendance count using the same logic as the working Attendance API
        attendance_count = 0
        if class_id and jam_awal and jam_akhir and (status == "Selesai" or status == "Sedang Berlangsung"):
            try:
                # Use the same datetime parsing logic as the working API
                meeting_date_str = pertemuan_date.strftime("%Y-%m-%d")
                start_time = datetime.strptime(f"{meeting_date_str} {jam_awal}", "%Y-%m-%d %H:%M")
                end_time = datetime.strptime(f"{meeting_date_str} {jam_akhir}", "%Y-%m-%d %H:%M")
                
                # Use the same aggregation pipeline as the working API
                pipeline = [
                    {"$addFields": {
                        "timestamp_date": {"$toDate": "$timestamp"}
                    }},
                    {"$match": {
                        "timestamp_date": {"$gte": start_time, "$lte": end_time},
                        "$or": [
                            {"class_id": str(class_id)},
                            {"class_id": class_id}
                        ]
                    }},
                    {"$lookup": {
                        "from": "Users",
                        "localField": "user_id",
                        "foreignField": "_id",
                        "as": "student_info"
                    }},
                    {"$project": {
                        "timestamp": 1,
                        "full_name": {
                            "$cond": [
                                {"$gt": [{"$size": "$student_info"}, 0]},
                                {"$arrayElemAt": ["$student_info.name", 0]},
                                "Unknown"
                            ]
                        }
                    }}
                ]
                
                results = list(attendance_collection.aggregate(pipeline))
                attendance_count = len(results)
                
                print(f"[DEBUG] Pertemuan {i} ({meeting_date_str}): Found {attendance_count} attendance records")
                
            except Exception as e:
                print(f"[DEBUG] Error calculating attendance for Pertemuan {i}: {e}")
                attendance_count = 0
        
        pertemuan_list.append({
            "pertemuan": i,
            "tanggal": pertemuan_date.isoformat(),
            "status": status,
            "present_count": attendance_count,
            "total_enrolled": total_enrolled,
            "attendance_ratio": f"{attendance_count}/{total_enrolled}" if total_enrolled > 0 else "0/0"
        })
    
    return pertemuan_list

def calculate_pertemuan_status(tanggal_awal, current_date=None):
    """Calculate the status of 16 Pertemuan based on tanggal_awal and current date"""
    if current_date is None:
        current_date = datetime.now().date()
    
    # Convert tanggal_awal to date if it's datetime
    if isinstance(tanggal_awal, datetime):
        start_date = tanggal_awal.date()
    else:
        start_date = tanggal_awal
    
    pertemuan_list = []
    
    for i in range(1, 17):  # Pertemuan 1 to 16
        # Calculate the date for this pertemuan (weekly intervals)
        pertemuan_date = start_date + timedelta(weeks=i-1)
        
        # Determine status based on current date
        if pertemuan_date < current_date:
            status = "Selesai"
        elif pertemuan_date == current_date:
            status = "Sedang Berlangsung"
        else:
            status = "Belum Dimulai"
        
        pertemuan_list.append({
            "pertemuan": i,
            "tanggal": pertemuan_date.isoformat(),
            "status": status
        })
    
    return pertemuan_list

def normalize_object_id(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        try:
            return ObjectId(value)
        except Exception:
            return None
    return None

def build_class_match_filters(class_id, fallback_id):
    filters = []

    def add_filter(candidate):
        if candidate is None:
            return
        filters.append({"class_id": candidate})
        if isinstance(candidate, ObjectId):
            filters.append({"class_id": str(candidate)})
        elif isinstance(candidate, str):
            try:
                filters.append({"class_id": ObjectId(candidate)})
            except Exception:
                pass

    add_filter(class_id)
    if not filters:
        add_filter(fallback_id)
        add_filter(str(fallback_id))

    if not filters:
        return [{"class_id": fallback_id}]
    return filters

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
            d[key] = value.isoformat()  # Convert datetime to ISO string format
    
    return d

@router.get("/test", tags=["Matkul"])
async def test_matkul_route():
    """Test endpoint to verify Matkul router is working"""
    return {"message": "Matkul router is working!", "status": "success"}

@router.get("/", tags=["Matkul"])
async def get_matkul_by_dosen(current_user: dict = Depends(get_current_user)):
    """Get all Matkul (courses) taught by the logged-in lecturer"""
    try:
        account_id = ObjectId(current_user["account_id"])
        print(f"[DEBUG] Searching for Matkul with account_id: {account_id}")
    except Exception as e:
        print(f"[ERROR] Invalid account ID: {e}")
        raise HTTPException(status_code=400, detail="Invalid account ID")
    
    try:
        # Find all Matkul where account_id matches the current user's account_id
        matkul_cursor = matkul_collection.find({"account_id": account_id})
        matkul_list = []
        
        for matkul in matkul_cursor:
            print(f"[DEBUG] Processing Matkul: {matkul.get('nama_matkul', 'Unknown')}")
            matkul_normalized = normalize_doc(matkul)
            
            # Calculate Pertemuan status with attendance data
            if "tanggal_awal" in matkul_normalized:
                try:
                    # Parse tanggal_awal if it's a string
                    tanggal_awal = matkul.get("tanggal_awal")
                    if isinstance(tanggal_awal, str):
                        tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
                    
                    matkul_normalized["pertemuan_list"] = calculate_pertemuan_with_attendance(
                        tanggal_awal, 
                        matkul["_id"],
                        matkul.get("nama_matkul", "")
                    )
                    print(f"[DEBUG] Added {len(matkul_normalized['pertemuan_list'])} pertemuan with attendance for {matkul_normalized.get('nama_matkul')}")
                except Exception as e:
                    print(f"[DEBUG] Could not calculate pertemuan status with attendance: {e}")
                    matkul_normalized["pertemuan_list"] = []
            
            # Get class information if class_id exists
            if "class_id" in matkul_normalized and matkul_normalized["class_id"]:
                try:
                    class_obj_id = ObjectId(matkul_normalized["class_id"])
                    class_info = class_collection.find_one({"_id": class_obj_id})
                    if class_info:
                        matkul_normalized["class_info"] = normalize_doc(class_info)
                        print(f"[DEBUG] Added class_info for {matkul_normalized.get('nama_matkul')}")
                    else:
                        print(f"[DEBUG] No class found for class_id: {class_obj_id}")
                except Exception as e:
                    print(f"[DEBUG] Could not fetch class info: {e}")
                    # If class_id is not a valid ObjectId, skip class lookup
                    pass
            
            matkul_list.append(matkul_normalized)
        
        print(f"[DEBUG] Returning {len(matkul_list)} Matkul records")
        return JSONResponse(content=matkul_list)
        
    except Exception as e:
        print(f"[ERROR] Error in get_matkul_by_dosen: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/debug", tags=["Matkul"])
async def debug_matkul_data(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to see current user and sample Matkul data"""
    
    account_id = ObjectId(current_user["account_id"])
    
    # Count documents for this user
    user_matkul_count = matkul_collection.count_documents({"account_id": account_id})
    total_count = matkul_collection.count_documents({})
    
    return {
        "user_account_id": current_user["account_id"],
        "user_matkul_count": user_matkul_count,
        "total_matkul_count": total_count,
        "message": "Simple debug info"
    }

@router.get("/{matkul_id}/report-summary", tags=["Matkul"])
async def get_matkul_report_summary(matkul_id: str, current_user: dict = Depends(get_current_user)):
    try:
        matkul_obj_id = ObjectId(matkul_id)
        account_id = ObjectId(current_user["account_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    matkul = matkul_collection.find_one({"_id": matkul_obj_id, "account_id": account_id})
    if not matkul:
        raise HTTPException(status_code=404, detail="Matkul not found or not authorized")

    tanggal_awal = matkul.get("tanggal_awal")
    if tanggal_awal is None:
        raise HTTPException(status_code=400, detail="Matkul is missing tanggal_awal")
    if isinstance(tanggal_awal, str):
        try:
            tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tanggal_awal format")

    pertemuan_list = calculate_pertemuan_with_attendance(
        tanggal_awal,
        matkul["_id"],
        matkul.get("nama_matkul", "")
    )

    class_id = matkul.get("class_id")
    class_filters = build_class_match_filters(class_id, matkul_obj_id)

    match_conditions = {"$or": class_filters}
    attendance_pipeline = [
        {"$match": {
            "$and": [
                {"user_id": {"$ne": None}},
                match_conditions
            ]
        }},
        {"$group": {"_id": "$user_id", "attended_sessions": {"$sum": 1}}}
    ]

    attendance_results = list(attendance_collection.aggregate(attendance_pipeline))
    attendance_counts = {}
    for record in attendance_results:
        if record.get("_id") is None:
            continue
        attendance_counts[str(record["_id"])] = record.get("attended_sessions", 0)

    completed_sessions = [p for p in pertemuan_list if p.get("status") != "Belum Dimulai"]
    total_sessions = len(completed_sessions) if completed_sessions else len(pertemuan_list)
    effective_sessions = total_sessions if total_sessions > 0 else 1

    enrolled_docs = list(rps_collection.find({"matkul_id": matkul_obj_id}))
    user_lookup_ids = []

    for doc in enrolled_docs:
        normalized = normalize_object_id(doc.get("user_id"))
        if normalized:
            user_lookup_ids.append(normalized)

    for raw_id in attendance_counts.keys():
        normalized = normalize_object_id(raw_id)
        if normalized and normalized not in user_lookup_ids:
            user_lookup_ids.append(normalized)

    user_name_map = {}
    if user_lookup_ids:
        unique_lookup_ids = list({str(_id): _id for _id in user_lookup_ids}.values())
        user_docs = users_collection.find({"_id": {"$in": unique_lookup_ids}})
        for user in user_docs:
            user_name_map[str(user["_id"])] = user.get("name", "Mahasiswa")

    students_summary = []
    seen_ids = set()

    for doc in enrolled_docs:
        normalized = normalize_object_id(doc.get("user_id"))
        user_id_str = str(normalized) if normalized else str(doc.get("user_id"))
        seen_ids.add(user_id_str)
        attended = attendance_counts.get(user_id_str, 0)
        percent = round((attended / effective_sessions) * 100) if effective_sessions else 0
        students_summary.append({
            "user_id": user_id_str,
            "name": user_name_map.get(user_id_str, "Mahasiswa"),
            "attendance_percent": percent,
            "attended_sessions": attended,
            "total_sessions": total_sessions,
        })

    for uid_str, attended in attendance_counts.items():
        if uid_str in seen_ids:
            continue
        percent = round((attended / effective_sessions) * 100) if effective_sessions else 0
        students_summary.append({
            "user_id": uid_str,
            "name": user_name_map.get(uid_str, "Mahasiswa"),
            "attendance_percent": percent,
            "attended_sessions": attended,
            "total_sessions": total_sessions,
        })

    trend_data = []
    history_data = []

    for pertemuan in pertemuan_list:
        total_enrolled = pertemuan.get("total_enrolled", 0) or 0
        present_count = pertemuan.get("present_count", 0) or 0
        percent = round((present_count / total_enrolled) * 100, 2) if total_enrolled else 0
        trend_data.append({
            "month": f"Mg {pertemuan.get('pertemuan')}",
            "attendance": percent
        })
        history_data.append({
            "pertemuan": f"Pertemuan {pertemuan.get('pertemuan')}",
            "tanggal": pertemuan.get("tanggal"),
            "kehadiran": f"{present_count}/{total_enrolled}"
        })

    distribution_template = [
        {"range": "<50%", "students": 0},
        {"range": "50-70%", "students": 0},
        {"range": "70-90%", "students": 0},
        {"range": ">90%", "students": 0},
    ]

    for student in students_summary:
        percent = student.get("attendance_percent", 0)
        if percent < 50:
            distribution_template[0]["students"] += 1
        elif percent < 70:
            distribution_template[1]["students"] += 1
        elif percent < 90:
            distribution_template[2]["students"] += 1
        else:
            distribution_template[3]["students"] += 1

    return {
        "trend": trend_data,
        "distribution": distribution_template,
        "students": students_summary,
        "pertemuan_history": history_data,
        "default_student_id": students_summary[0]["user_id"] if students_summary else None,
    }

@router.get("/{matkul_id}", tags=["Matkul"])
async def get_matkul_by_id(matkul_id: str, current_user: dict = Depends(get_current_user)):
    """Get specific Matkul by ID (only if taught by current lecturer)"""
    try:
        matkul_obj_id = ObjectId(matkul_id)
        account_id = ObjectId(current_user["account_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    
    matkul = matkul_collection.find_one({
        "_id": matkul_obj_id,
        "account_id": account_id
    })
    
    if not matkul:
        raise HTTPException(status_code=404, detail="Matkul not found or not authorized")
    
    matkul_normalized = normalize_doc(matkul)
    
    # Get class information if ruangan_id exists
    if "ruangan_id" in matkul_normalized:
        try:
            ruangan_obj_id = ObjectId(matkul_normalized["ruangan_id"])
            class_info = class_collection.find_one({"_id": ruangan_obj_id})
            if class_info:
                matkul_normalized["ruangan_info"] = normalize_doc(class_info)
        except Exception:
            pass
    
    return JSONResponse(content=matkul_normalized)