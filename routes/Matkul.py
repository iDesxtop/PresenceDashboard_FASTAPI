from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse
from typing import List
from config.configrations import matkul_collection, class_collection, db, users_collection, kelas_spesial_collection, attendance_spesial_collection
from models.KelasSpesial import RescheduleRequest, KelasSpesialModel, ManualAttendanceRequest
from bson import ObjectId
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from datetime import datetime, timedelta, timezone

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
    # Shift to UTC+7 (WIB) to match "Fake UTC" data
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    
    if current_date is None:
        current_date = now_wib.date()
    
    # Convert tanggal_awal to date if it's datetime
    if isinstance(tanggal_awal, datetime):
        start_date = tanggal_awal.date()
    else:
        start_date = tanggal_awal
    
    # Get total enrolled students for this Matkul
    try:
        matkul_obj_id = ObjectId(matkul_id)
        # Use distinct to count unique students, avoiding duplicates in RPS
        total_enrolled = len(rps_collection.distinct("user_id", {"matkul_id": matkul_obj_id}))
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
        
        # Check for overrides (Reschedule)
        jam_awal_curr = jam_awal
        jam_akhir_curr = jam_akhir
        class_id_curr = class_id
        
        override_data = kelas_spesial_collection.find_one({
            "matkul_id": matkul_obj_id,
            "pertemuan": i
        })
        
        if override_data:
            if override_data.get("tanggal_kelas"):
                tk = override_data.get("tanggal_kelas")
                if isinstance(tk, datetime):
                    pertemuan_date = tk.date()
                elif isinstance(tk, str):
                    try:
                        pertemuan_date = datetime.fromisoformat(tk.replace('Z', '+00:00')).date()
                    except:
                        pass
            
            if override_data.get("jam_awal"): jam_awal_curr = override_data.get("jam_awal")
            if override_data.get("jam_akhir"): jam_akhir_curr = override_data.get("jam_akhir")
            # If is_online is True, class_id might be None, which is fine
            if "class_id" in override_data: class_id_curr = override_data.get("class_id")

        # Determine is_rescheduled
        is_rescheduled = True if override_data else False

        meeting_date_str = pertemuan_date.strftime("%Y-%m-%d")

        # Determine status based on current date (Using Adjusted WIB Time)
        if pertemuan_date < current_date:
            status = "Selesai"
        elif pertemuan_date == current_date:
            current_time_str = now_wib.strftime("%H:%M")
            if jam_akhir_curr and current_time_str > jam_akhir_curr:
                status = "Selesai"
            elif jam_awal_curr and current_time_str < jam_awal_curr:
                status = "Belum Dimulai"
            else:
                status = "Sedang Berlangsung"
        else:
            status = "Belum Dimulai"
        
        # Get attendance count
        attendance_count = 0
        if override_data:
            # Rescheduled class: Use Manual Attendance logic
            # Count how many students are present (record exists in Attendance_Spesial)
            try:
                # UNIFIED LOGIC: Just count documents. 
                # This works regardless of timestamp format (Object vs String) as long as IDs match.
                attendance_count = attendance_spesial_collection.count_documents({
                    "spesial_id": override_data["_id"]
                })
            except Exception as e:
                print(f"[DEBUG] Error counting manual attendance: {e}")
                attendance_count = 0
        elif jam_awal_curr and jam_akhir_curr and (status == "Selesai" or status == "Sedang Berlangsung"):
            # Original class: Use Automatic Camera Attendance
            try:
                # Use the same datetime parsing logic as the working API
                start_time = datetime.strptime(f"{meeting_date_str} {jam_awal_curr}", "%Y-%m-%d %H:%M")
                end_time = datetime.strptime(f"{meeting_date_str} {jam_akhir_curr}", "%Y-%m-%d %H:%M")
                
                # Use the same aggregation pipeline as the working API
                pipeline = [
                    {"$addFields": {
                        "timestamp_date": {"$toDate": "$timestamp"}
                    }},
                    {"$match": {
                        "timestamp_date": {"$gte": start_time, "$lte": end_time},
                        "$or": build_class_match_filters(class_id_curr, matkul_obj_id)
                    }},
                    {"$group": {
                        "_id": "$user_id" # Count unique users
                    }}
                ]
                
                results = list(attendance_collection.aggregate(pipeline))
                attendance_count = len(results)
                
            except Exception as e:
                print(f"[DEBUG] Error calculating attendance for Pertemuan {i}: {e}")
                attendance_count = 0
        
        pertemuan_list.append({
            "pertemuan": i,
            "tanggal": pertemuan_date.isoformat(),
            "status": status,
            "present_count": attendance_count,
            "total_enrolled": total_enrolled,
            "attendance_ratio": f"{attendance_count}/{total_enrolled}" if total_enrolled > 0 else "0/0",
            "is_rescheduled": is_rescheduled,
            "jam_awal": jam_awal_curr,
            "jam_akhir": jam_akhir_curr
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

@router.get("/attendance-distribution", tags=["Matkul"])
async def get_attendance_distribution(current_user: dict = Depends(get_current_user)):
    try:
        account_id = ObjectId(current_user["account_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid account ID")

    matkul_cursor = matkul_collection.find({"account_id": account_id})
    class_stats: dict[str, dict] = {}

    for matkul in matkul_cursor:
        matkul_id = matkul.get("_id")
        if not matkul_id:
            continue

        nama_matkul = matkul.get("nama_matkul", "Mata Kuliah")
        class_key = str(matkul.get("class_id") or matkul_id)

        # Hitung mahasiswa unik yang terdaftar pada matkul ini
        enrolled_user_ids = [uid for uid in rps_collection.distinct("user_id", {"matkul_id": matkul_id}) if uid is not None]
        total_enrolled = len(enrolled_user_ids)

        class_filters = build_class_match_filters(matkul.get("class_id"), matkul_id)

        session_pipeline = [
            {"$match": {
                "$and": [
                    {"user_id": {"$ne": None}},
                    {"$or": class_filters}
                ]
            }},
            {"$addFields": {"timestamp_date": {"$toDate": "$timestamp"}}},
            {"$match": {"timestamp_date": {"$ne": None}}},
            {"$project": {
                "user_id": 1,
                "timestamp_date": 1,
                "session_key": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp_date"}}
            }},
            {"$match": {"session_key": {"$ne": None}}},
            {"$group": {
                "_id": {"session_key": "$session_key", "user_id": "$user_id"},
                "first_timestamp": {"$min": "$timestamp_date"}
            }},
            {"$group": {
                "_id": "$_id.session_key",
                "first_timestamp": {"$min": "$first_timestamp"},
                "attendees": {"$addToSet": "$_id.user_id"}
            }},
            {"$sort": {"first_timestamp": 1}}
        ]

        session_results = list(attendance_collection.aggregate(session_pipeline))
        session_count = len(session_results)
        total_attendance = 0
        unique_attendees = set()
        for session in session_results:
            attendees = [str(uid) for uid in session.get("attendees", []) if uid is not None]
            total_attendance += len(attendees)
            unique_attendees.update(attendees)

        max_capacity = session_count * total_enrolled if session_count and total_enrolled else 0

        if total_enrolled == 0 and unique_attendees:
            total_enrolled = len(unique_attendees)
            max_capacity = session_count * total_enrolled if session_count else total_attendance

        if max_capacity == 0 and total_attendance > 0:
            max_capacity = total_attendance

        percentage = round((total_attendance / max_capacity) * 100, 2) if max_capacity else 0

        stats_payload = {
            "matkul_id": str(matkul_id),
            "nama_matkul": nama_matkul,
            "attendance_count": total_attendance,
            "total_enrolled": total_enrolled,
            "attendance_percent": percentage,
            "session_count": session_count,
            "max_capacity": max_capacity,
        }

        existing = class_stats.get(class_key)
        chosen = False
        if not existing:
            chosen = True
        else:
            if stats_payload.get("max_capacity", 0) > existing.get("max_capacity", 0):
                chosen = True
            elif stats_payload.get("total_enrolled", 0) > existing.get("total_enrolled", 0):
                chosen = True

        if chosen:
            class_stats[class_key] = stats_payload

    distribution = list(class_stats.values())
    distribution.sort(key=lambda item: item["nama_matkul"])
    return distribution

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
        {"$addFields": {
            "timestamp_date": {"$toDate": "$timestamp"}
        }},
        {"$match": {"timestamp_date": {"$ne": None}}},
        {"$addFields": {
            "session_key": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp_date"}
            }
        }},
        {"$match": {"session_key": {"$ne": None}}},
        {"$group": {
            "_id": {"user_id": "$user_id", "session_key": "$session_key"}
        }},
        {"$group": {"_id": "$_id.user_id", "attended_sessions": {"$sum": 1}}}
    ]

    attendance_results = list(attendance_collection.aggregate(attendance_pipeline))
    attendance_counts = {}
    for record in attendance_results:
        if record.get("_id") is None:
            continue
        attendance_counts[str(record["_id"])] = record.get("attended_sessions", 0)

    completed_sessions = [p for p in pertemuan_list if p.get("status") != "Belum Dimulai"]
    scheduled_sessions = len(completed_sessions) if completed_sessions else len(pertemuan_list)
    max_attended_sessions = max(attendance_counts.values(), default=0)
    effective_sessions = max(scheduled_sessions, max_attended_sessions, 1)

    enrolled_docs = list(rps_collection.find({"matkul_id": matkul_obj_id}))
    enrolled_user_map = {}

    for doc in enrolled_docs:
        normalized = normalize_object_id(doc.get("user_id"))
        if normalized:
            enrolled_user_map[str(normalized)] = normalized

    total_enrolled_count = len(enrolled_user_map)
    user_lookup_ids = list(enrolled_user_map.values())

    for raw_id in attendance_counts.keys():
        normalized = normalize_object_id(raw_id)
        if normalized and str(normalized) not in enrolled_user_map:
            enrolled_user_map[str(normalized)] = normalized
            user_lookup_ids.append(normalized)

    if total_enrolled_count == 0:
        total_enrolled_count = len(enrolled_user_map)

    display_total_enrolled = total_enrolled_count

    for pertemuan in pertemuan_list:
        pertemuan_total = display_total_enrolled if display_total_enrolled else pertemuan.get("total_enrolled", 0)
        pertemuan["total_enrolled"] = pertemuan_total
        present_count = pertemuan.get("present_count", 0) or 0
        denominator = pertemuan_total or 0
        if denominator:
            pertemuan["attendance_ratio"] = f"{present_count}/{denominator}"
        else:
            pertemuan["attendance_ratio"] = f"{present_count}/0"

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
        if not user_id_str or user_id_str in seen_ids:
            continue
        seen_ids.add(user_id_str)
        attended = attendance_counts.get(user_id_str, 0)
        percent = round((attended / effective_sessions) * 100) if effective_sessions else 0
        students_summary.append({
            "user_id": user_id_str,
            "name": user_name_map.get(user_id_str, "Mahasiswa"),
            "attendance_percent": percent,
            "attended_sessions": attended,
            "total_sessions": effective_sessions,
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
            "total_sessions": effective_sessions,
        })

    trend_data = []
    history_data = []

    for pertemuan in pertemuan_list:
        pertemuan_number = pertemuan.get("pertemuan")
        present_count = pertemuan.get("present_count", 0) or 0
        total_enrolled_value = pertemuan.get("total_enrolled", 0)

        history_data.append({
            "pertemuan": f"Pertemuan {pertemuan_number}",
            "tanggal": pertemuan.get("tanggal"),
            "kehadiran": pertemuan.get("attendance_ratio", f"{present_count}/{total_enrolled_value}"),
        })

        if pertemuan.get("status") == "Belum Dimulai":
            continue

        capacity = total_enrolled_value if total_enrolled_value else max(present_count, 1)
        percent = round((present_count / capacity) * 100, 2) if capacity else 0
        trend_data.append({
            "month": f"Mg {pertemuan_number}",
            "attendance": percent
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

@router.get("/{matkul_id}/pertemuan/{pertemuan_ke}", tags=["Matkul"])
async def get_pertemuan_detail(
    matkul_id: str,
    pertemuan_ke: int,
    current_user: dict = Depends(get_current_user)
):
    try:
        matkul_obj_id = ObjectId(matkul_id)
        account_id = ObjectId(current_user["account_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    matkul = matkul_collection.find_one({"_id": matkul_obj_id, "account_id": account_id})
    if not matkul:
        raise HTTPException(status_code=404, detail="Matkul not found or not authorized")

    tanggal_awal = matkul.get("tanggal_awal")
    if not tanggal_awal:
        raise HTTPException(status_code=400, detail="Matkul is missing tanggal_awal")
    
    if isinstance(tanggal_awal, str):
        try:
            tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tanggal_awal format")

    if isinstance(tanggal_awal, datetime):
        start_date = tanggal_awal.date()
    else:
        start_date = tanggal_awal

    jam_awal = matkul.get("jam_awal")
    jam_akhir = matkul.get("jam_akhir")
    class_id = matkul.get("class_id")

    # Calculate meeting date
    pertemuan_date = start_date + timedelta(weeks=pertemuan_ke - 1)
    
    # Check for overrides
    jam_awal_curr = jam_awal
    jam_akhir_curr = jam_akhir
    class_id_curr = class_id
    
    override_data = kelas_spesial_collection.find_one({
        "matkul_id": matkul_obj_id, 
        "pertemuan": pertemuan_ke
    })
    
    if override_data:
        if override_data.get("tanggal_kelas"):
             tk = override_data.get("tanggal_kelas")
             if isinstance(tk, datetime):
                 pertemuan_date = tk.date()
             elif isinstance(tk, str):
                 try:
                     pertemuan_date = datetime.fromisoformat(tk.replace('Z', '+00:00')).date()
                 except: 
                     pass
        if override_data.get("jam_awal"): jam_awal_curr = override_data.get("jam_awal")
        if override_data.get("jam_akhir"): jam_akhir_curr = override_data.get("jam_akhir")
        if "class_id" in override_data: class_id_curr = override_data.get("class_id")

    meeting_date_str = pertemuan_date.strftime("%Y-%m-%d")

    # Determine status (Adjusted Key Logic: UTC+7)
    # Align "Current Real Time" to "Fake UTC Data Time" which is secretly Local Time.
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    current_date_obj = now_wib.date()

    if pertemuan_date < current_date_obj:
        status = "Selesai"
    elif pertemuan_date == current_date_obj:
        current_time_str = now_wib.strftime("%H:%M")
        
        # DEBUG: Log logic for Sedang Berlangsung verification
        print(f"[DEBUG STATUS] Pertemuan {pertemuan_ke}: Now(WIB)={current_time_str} vs Schedule(FakeUTC)={jam_awal_curr}-{jam_akhir_curr}")

        if jam_akhir_curr and current_time_str > jam_akhir_curr:
            status = "Selesai"
        elif jam_awal_curr and current_time_str < jam_awal_curr:
            status = "Belum Dimulai"
        else:
            status = "Sedang Berlangsung"
    else:
        status = "Belum Dimulai"

    # Get Enrolled Students
    enrolled_docs = list(rps_collection.find({"matkul_id": matkul_obj_id}))
    
    unique_user_ids = []
    seen_ids = set()
    for doc in enrolled_docs:
        uid = normalize_object_id(doc.get("user_id"))
        if uid and str(uid) not in seen_ids:
            seen_ids.add(str(uid))
            unique_user_ids.append(uid)
            
    user_ids = unique_user_ids
    
    # Fetch User Details
    user_map = {}
    if user_ids:
        users = users_collection.find({"_id": {"$in": user_ids}})
        for u in users:
            user_map[str(u["_id"])] = {
                "name": u.get("name", "Unknown"),
                "nim": u.get("nim", "-") # Assuming 'nim' exists in Users
            }

    # Get Attendance Records
    attendance_records = {} # Format: {user_id: timestamp_str}
    
    is_rescheduled = True if override_data else False
    
    if override_data:
        # ---------------------------------------------------------
        # Rescheduled Class -> Read from Attendance_Spesial (Manual)
        # Using spesial_id from Kelas_Spesial
        # ---------------------------------------------------------
        try:
            manual_records = list(attendance_spesial_collection.find({
                "spesial_id": override_data["_id"]
            }))
            
            for record in manual_records:
                # user_id stored in Attendance_Spesial is ObjectId? Let's check how it's saved.
                # In /attendance-manual, we do `student_obj_id = ObjectId(payload.student_id)`
                # Then save "user_id": student_obj_id
                # So we must convert ObjectId to string here
                uid = str(record.get("user_id"))
                ts = record.get("timestamp")
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                elif isinstance(ts, str):
                    pass
                else:
                    ts = "-" # Manual record might not have timestamp if not set
                attendance_records[uid] = ts
        except Exception as e:
            print(f"Error fetching manual attendance: {e}")

    # Use current params (handling rescheduled times/classes for Automatic Check)
    # Only if NOT rescheduled (original flow) or if we want hybrid? 
    # Requirement: "only for the userflow of dosen changing schedules... CRUD attendance with camera... should be preserved"
    # implies mutually exclusive flows based on whether schedule changed.
    elif jam_awal_curr and jam_akhir_curr:
        # ---------------------------------------------------------
        # Standard Class -> Read from Attendance (Automatic/Camera)
        # ---------------------------------------------------------
        try:
            start_time = datetime.strptime(f"{meeting_date_str} {jam_awal_curr}", "%Y-%m-%d %H:%M")
            end_time = datetime.strptime(f"{meeting_date_str} {jam_akhir_curr}", "%Y-%m-%d %H:%M")
            
            pipeline = [
                {"$addFields": {
                    "timestamp_date": {"$toDate": "$timestamp"}
                }},
                {"$match": {
                    "timestamp_date": {"$gte": start_time, "$lte": end_time},
                    "$or": build_class_match_filters(class_id_curr, matkul_obj_id)
                }},
                {"$project": {
                    "user_id": 1,
                    "timestamp": 1
                }}
            ]
            
            attendees = list(attendance_collection.aggregate(pipeline))
            for a in attendees:
                uid = str(a.get("user_id"))
                ts = a.get("timestamp")
                
                # Robust timestamp handling (Same as Rescheduled logic)
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                elif isinstance(ts, str):
                    pass
                else:
                    ts = "-"
                
                # Store earliest timestamp if multiple
                if uid not in attendance_records:
                    attendance_records[uid] = ts
                
        except Exception as e:
            print(f"Error fetching attendance: {e}")

    # Merge Data
    student_list = []
    present_count = 0
    
    for uid_obj in user_ids:
        uid = str(uid_obj)
        user_info = user_map.get(uid, {"name": "Unknown", "nim": "-"})
        
        is_present = uid in attendance_records
        if is_present:
            present_count += 1
            
        student_list.append({
            "id": uid,
            "name": user_info["name"],
            "nim": user_info["nim"], 
            "status": "Hadir" if is_present else "Tidak Hadir",
            "waktu_absen": attendance_records.get(uid, "-")
        })

    return {
        "matkul_name": matkul.get("nama_matkul"),
        "pertemuan": pertemuan_ke,
        "tanggal": meeting_date_str,
        "status": status,
        "total_mahasiswa": len(student_list),
        "hadir": present_count,
        "tidak_hadir": len(student_list) - present_count,
        "students": student_list,
        "jam_awal": jam_awal_curr,
        "jam_akhir": jam_akhir_curr,
        "is_rescheduled": is_rescheduled
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

@router.post("/reschedule", tags=["Matkul"])
async def reschedule_class(payload: RescheduleRequest, current_user: dict = Depends(get_current_user)):
    """
    Reschedule or move a class meeting.
    If is_online is True, class_id will be set to None.
    Creates or updates a Kelas_Spesial entry.
    """
    try:
        matkul_obj_id = ObjectId(payload.matkul_id)
        # Verify ownership
        account_id = ObjectId(current_user["account_id"])
        
        matkul = matkul_collection.find_one({
            "_id": matkul_obj_id,
            "account_id": account_id
        })
        
        if not matkul:
            raise HTTPException(status_code=404, detail="Matkul not found or not authorized")

        class_obj_id = None
        if not payload.is_online and payload.class_id:
            try:
                class_obj_id = ObjectId(payload.class_id)
                # Verify class exists
                if not class_collection.find_one({"_id": class_obj_id}):
                     raise HTTPException(status_code=404, detail="Classroom not found")
            except:
                 raise HTTPException(status_code=400, detail="Invalid Class ID")
        
        # Prepare data
        query = {
            "matkul_id": matkul_obj_id,
            "pertemuan": payload.pertemuan
        }
        
        # Parse datetime for validation/storage
        try:
             # Construct full datetime for 'tanggal_kelas' using date + start time
             dt_str = f"{payload.tanggal_baru}T{payload.jam_mulai_baru}:00"
             # Create a datetime object first to validate
             dt_obj = datetime.fromisoformat(dt_str)
             # Store as STRING ending in Z (Unified Format)
             tanggal_kelas = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date/time format: {e}")

        update_data = {
            "matkul_id": matkul_obj_id,
            "class_id": class_obj_id, # Null if online
            "pertemuan": payload.pertemuan,
            "jam_awal": payload.jam_mulai_baru,
            "jam_akhir": payload.jam_selesai_baru,
            "tanggal_kelas": tanggal_kelas, # Stored as String "2025-...Z"
            "is_online": payload.is_online
        }
        
        # Upsert
        result = kelas_spesial_collection.update_one(
            query, 
            {"$set": update_data}, 
            upsert=True
        )
        
        return {"status": "success", "message": "Class rescheduled successfully"}
        
    except Exception as e:
        print(f"Error rescheduling: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/attendance-manual", tags=["Matkul"])
async def manual_attendance(payload: ManualAttendanceRequest, current_user: dict = Depends(get_current_user)):
    """
    Manually update attendance for Any class (Regular or Rescheduled).
    - If Rescheduled (Kelas_Spesial exists): Updates Attendance_Spesial.
    - If Regular (No Kelas_Spesial): Updates Attendance (Camera logs).
    """
    try:
        matkul_obj_id = ObjectId(payload.matkul_id)
        student_obj_id = ObjectId(payload.student_id)
        account_id = ObjectId(current_user["account_id"])

        # 1. Verify Matkul ownership
        matkul = matkul_collection.find_one({
            "_id": matkul_obj_id,
            "account_id": account_id
        })
        if not matkul:
            raise HTTPException(status_code=404, detail="Matkul not found or not authorized")
        
        # 2. Check for Reschedule Entry
        override_data = kelas_spesial_collection.find_one({
            "matkul_id": matkul_obj_id,
            "pertemuan": payload.pertemuan
        })
        
        # Prepare Timestamp
        # Use provided timestamp or default to Now (WIB/Fake UTC)
        # We need to default to the User's Local Time (WIB) because that's what the system treats as "Z" time.
        now_wib_ts = datetime.now(timezone.utc) + timedelta(hours=7)
        
        if payload.timestamp:
            try:
                attendance_ts = datetime.fromisoformat(payload.timestamp.replace('Z', '+00:00'))
            except:
                attendance_ts = now_wib_ts
        else:
             attendance_ts = now_wib_ts

        # -------------------------------------------------------------
        # CHECK: Cannot update attendance if class hasn't started yet!
        # -------------------------------------------------------------
        now_utc = datetime.now(timezone.utc)
        start_datetime = None
        jam_awal_check = None
        pertemuan_date_check = None

        if override_data:
             # Logic for Rescheduled Date
             if override_data.get("tanggal_kelas"):
                 tk = override_data.get("tanggal_kelas")
                 if isinstance(tk, datetime):
                     pertemuan_date_check = tk.date()
                 elif isinstance(tk, str):
                     try:
                        pertemuan_date_check = datetime.fromisoformat(tk.replace('Z', '+00:00')).date()
                     except: pass
             if override_data.get("jam_awal"): jam_awal_check = override_data.get("jam_awal")
        else:
            # Logic for Regular Date
            tanggal_awal = matkul.get("tanggal_awal")
            if isinstance(tanggal_awal, str):
                tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
            if isinstance(tanggal_awal, datetime):
                start_date = tanggal_awal.date()
            else:
                start_date = tanggal_awal
            
            pertemuan_date_check = start_date + timedelta(weeks=payload.pertemuan - 1)
            jam_awal_check = matkul.get("jam_awal")

        # Perform Check
        if pertemuan_date_check and jam_awal_check:
            # Construct comparison time
            # ADJUSTMENT: Convert Real UTC to "Fake UTC/WIB" (+7 Hours)
            # This aligns the Current Time with the Class Schedule Data (which is secretly Local Time)
            now_wib = now_utc + timedelta(hours=7)
            
            current_date_obj = now_wib.date()
            can_edit = False
            
            if pertemuan_date_check < current_date_obj:
                can_edit = True
            elif pertemuan_date_check == current_date_obj:
                current_time_str = now_wib.strftime("%H:%M")
                # If current time >= start time, it has started
                if current_time_str >= jam_awal_check: 
                    can_edit = True
            
            if not can_edit:
                 raise HTTPException(status_code=400, detail="Cannot edit attendance: Class has not started yet (Belum Dimulai).")


        if override_data:
            # --- Rescheduled Class (Attendance_Spesial) ---
            filter_query = {
                "spesial_id": override_data["_id"],
                "user_id": student_obj_id
            }
            
            if payload.status:
                # Add (Upsert)
                # Store timestamp as ISO String with Z (Requested Unified Format)
                # Previous implementation used datetime object which becomes ISODate in Mongo.
                # User specifically requested "USE THE ONE WHERE IT ENDS WITH Z".
                ts_iso = attendance_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                
                update_doc = {
                    "spesial_id": override_data["_id"],
                    "user_id": student_obj_id,
                    "timestamp": ts_iso # String formatted as ISO with Z
                }
                attendance_spesial_collection.update_one(
                    filter_query,
                    {"$set": update_doc},
                    upsert=True
                )
            else:
                attendance_spesial_collection.delete_one(filter_query)
        
        else:
            # --- Regular Class (Attendance) ---
            # ... (Calculation of window) ...
            tanggal_awal = matkul.get("tanggal_awal")
            if isinstance(tanggal_awal, str):
                tanggal_awal = datetime.fromisoformat(tanggal_awal.replace('Z', '+00:00'))
            
            if isinstance(tanggal_awal, datetime):
                start_date = tanggal_awal.date()
            else:
                start_date = tanggal_awal
                
            pertemuan_date = start_date + timedelta(weeks=payload.pertemuan - 1)
            meeting_date_str = pertemuan_date.strftime("%Y-%m-%d")
            
            jam_awal = matkul.get("jam_awal")
            jam_akhir = matkul.get("jam_akhir")
            class_id = matkul.get("class_id")
            
            if not (jam_awal and jam_akhir):
                 raise HTTPException(status_code=400, detail="Cannot determine class schedule for regular attendance.")

            start_time = datetime.strptime(f"{meeting_date_str} {jam_awal}", "%Y-%m-%d %H:%M")
            end_time = datetime.strptime(f"{meeting_date_str} {jam_akhir}", "%Y-%m-%d %H:%M")
            
            # 1. DELETE EXISTING RECORDS FOR THIS USER IN THIS SESSION
            # This fixes "cant edit timestamp" for regular classes.
            # We remove conflict so the new manual entry is the source of truth.
            
            pipeline = [
                {"$addFields": {
                    "timestamp_date": {"$toDate": "$timestamp"}
                }},
                {"$match": {
                    "user_id": student_obj_id,
                    "timestamp_date": {"$gte": start_time, "$lte": end_time},
                    "$or": build_class_match_filters(class_id, matkul_obj_id)
                }},
                {"$project": {"_id": 1}}
            ]
            
            to_delete = list(attendance_collection.aggregate(pipeline))
            delete_ids = [d["_id"] for d in to_delete]
            
            if delete_ids:
                attendance_collection.delete_many({"_id": {"$in": delete_ids}})
            
            if payload.status:
                # 2. INSERT NEW RECORD
                # Format to ISO String with Z (Unified Format)
                # Matches the format used for Rescheduled classes
                ts_iso = attendance_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                
                insert_doc = {
                    "class_id": class_id,
                    "user_id": student_obj_id,
                    "timestamp": ts_iso, # String
                    "confidence": 1.0,
                    "source": "manual"
                }
                attendance_collection.insert_one(insert_doc)

        return {"status": "success", "message": "Attendance updated"}

        return {"status": "success", "message": "Attendance updated"}

    except Exception as e:
        print(f"Error manual attendance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
