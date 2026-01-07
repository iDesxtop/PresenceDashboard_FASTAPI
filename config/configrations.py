from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://muhammadalvinza_db_user:rN9p5EDVpwyjO8T2@basisdatanonrelasional.ydxgyls.mongodb.net/"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# # MongoDB Local URI
# uri = "mongodb://localhost:27017"

# # Create a new client and connect to the server
# client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["AbsensiCCTV"]
users_collection = db["Users"]
attendance_collection = db["Attendance"]
vector_collection = db["Vector"]
account_collection = db["Account"]
class_collection = db["Class"]
matkul_collection = db["Matkul"]
rps_collection = db["RPS"]
kelas_spesial_collection = db["Kelas_Spesial"]
attendance_spesial_collection = db["Attendance_Spesial"]