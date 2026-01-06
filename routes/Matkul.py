from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse
from typing import List
from config.configrations import matkul_collection, class_collection
from bson import ObjectId
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from datetime import datetime

SECRET_KEY = "your_secret_key"  # Use the same as in Account router
ALGORITHM = "HS256"

router = APIRouter()
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
            
            # Get class information if class_id exists
            if "class_id" in matkul_normalized and matkul_normalized["class_id"]:
                try:
                    class_obj_id = ObjectId(matkul_normalized["class_id"])
                    class_info = class_collection.find_one({"_id": class_obj_id})
                    if class_info:
                        matkul_normalized["class_info"] = normalize_doc(class_info)
                        print(f"[DEBUG] Added class_info for {matkul_normalized.get('nama_matkul')}")
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