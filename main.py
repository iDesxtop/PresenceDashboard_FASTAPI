from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.Users import router as users_router
from routes.Attendance import router as attendance_router
from routes.FaceOperation import router as face_router
from routes.Account import router as account_router
from routes.Class import router as class_router
from routes.Matkul import router as matkul_router
from routes.RPS import router as rps_router
from config.configrations import db

app = FastAPI()

# Use the existing database connection
app.database = db["SmartPresenceDatabase"]

# Tambahkan CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Atau spesifik: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],  # Mengizinkan semua method termasuk OPTIONS
    allow_headers=["*"],
)

# Include the Users router
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(attendance_router, prefix="/attendance", tags=["Attendance"])
app.include_router(face_router, tags=["FaceOperation"])
app.include_router(account_router, prefix="/account", tags=["Account"])
app.include_router(class_router, prefix="/class", tags=["Class"])
app.include_router(matkul_router, prefix="/matkul", tags=["Matkul"])
app.include_router(rps_router, prefix="/rps", tags=["RPS"])

@app.get("/")
async def read_root():
    return {"Hello": "World"}


