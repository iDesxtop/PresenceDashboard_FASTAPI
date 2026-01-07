"""
Sistem Face Recognition utama yang mengintegrasikan semua komponen
"""
from datetime import datetime, timedelta
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import shutil
import json
from tqdm import tqdm
from config.configrations import attendance_collection, users_collection, vector_collection
import base64
from bson import ObjectId
import time
from .timer import timerawal, timerstoptampilkantimer

from .config import (
    DATABASE_IMAGES_DIR,
    TESTING_IMAGES_DIR,
    RECOGNITION_THRESHOLD,
    SUPPORTED_EXTENSIONS,
)
from .face_detector import FaceDetector
from .face_encoder import FaceEncoder
from .database import FaceDatabase


class FaceRecognitionSystem:
    """
    Sistem Face Recognition lengkap untuk absensi
    """
    
    def __init__(self):
        """
        Inisialisasi sistem
        """
        print("="*50)
        print("Inisialisasi Face Recognition System")
        print("="*50)
        
        self.detector = FaceDetector()
        self.encoder = FaceEncoder()
        self.database = FaceDatabase()
        
        # Cache embeddings saat startup (bukan per-request)
        print("Loading embeddings ke cache...")
        self._cached_embeddings = []
        self._cached_visitor_embeddings = []
        self.refresh_embeddings_cache()
                
        print("="*50)
        print("Sistem siap digunakan!") 
        print("="*50)
    
    def refresh_embeddings_cache(self):
        """
        Refresh cache embeddings dari database.
        Panggil method ini setelah ada perubahan data embedding.
        """
        print("Refreshing embeddings cache...")
        self._cached_embeddings = self.database.get_all_embeddings()
        print(f"Cache updated: {len(self._cached_embeddings)} user embeddings")
    
    def extract_name_from_filename(self, filename: str) -> str:
        """
        Ekstrak nama dari filename.
        - Format lama: Name_1.jpg -> Name
        - Dukungan tambahan: 10_far, 10_mid, 10_near, 1_near, 2_far, dll -> kembalikan angka depan (kelas)
        """
        # Hapus ekstensi
        name_part = Path(filename).stem

        # Hapus suffix posisi jika ada (_far, _mid, _near) - case insensitive
        lowered = name_part.lower()
        for suffix in ("_far", "_mid", "_near"):
            if lowered.endswith(suffix):
                name_part = name_part[: len(name_part) - len(suffix)]
                break

        # Jika format Name_1 atau Name_1_anything, ambil bagian sebelum angka terakhir
        parts = name_part.rsplit("_", 1)
        if len(parts) > 1 and parts[-1].isdigit():
            return parts[0]

        # Jika seluruh stem adalah angka (contoh: "10" atau "2"), kembalikan angka itu
        if name_part.isdigit():
            return name_part

        return name_part
    
    def load_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Load gambar dari path
        
        Args:
            image_path: Path ke gambar
            
        Returns:
            Gambar dalam format BGR atau None jika gagal
        """
        image = cv2.imread(str(image_path))
        # image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if image is None:
            print(f"Warning: Gagal memuat gambar {image_path}")
        return image
    
    def register_faces_from_folder(self, folder_path: str = None, clear_existing: bool = True, dataset = DATABASE_IMAGES_DIR) -> Dict:
        """
        Daftarkan semua wajah dari folder ke database
        
        Args:
            folder_path: Path ke folder berisi gambar wajah
            clear_existing: Hapus data existing sebelum registrasi
            
        Returns:
            Dictionary dengan statistik registrasi
        """
        if folder_path is None:
            folder_path = dataset
        
        folder = Path(folder_path)
        
        if not folder.exists():
            raise ValueError(f"Folder tidak ditemukan: {folder}")
        
        # Get all image files
        image_files = [f for f in folder.iterdir() 
                      if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        
        if not image_files:
            raise ValueError(f"Tidak ada gambar ditemukan di {folder}")
        
        print(f"\nMendaftarkan wajah dari: {folder}")
        print(f"Ditemukan {len(image_files)} gambar")
        
        if clear_existing:
            # deleted_vector = vector_collection.clear_database()
            vector_collection.delete_many({})
            print(f"Database dibersihkan Vektor Colllection entri dihapus)")
        
        stats = {
            "total_images": len(image_files),
            "success": 0,
            "failed": 0,
            "persons": set()
        }
        
        for image_file in tqdm(image_files, desc="Mendaftarkan wajah"):
            person_name = self.extract_name_from_filename(image_file.name)
            print(f"Memproses: {image_file.name} (Nama: {person_name})")
            # Load image
            image = self.load_image(image_file)
            if image is None:
                stats["failed"] += 1
                continue
            
            # Detect face
            face = self.detector.detect_single_face(image)
            if face is None:
                print(f"Warning: Tidak ada wajah terdeteksi di {image_file.name}")
                stats["failed"] += 1
                continue
            
            # Get embedding
            embedding = self.encoder.get_embedding(face)
            if embedding is None:
                print(f"Warning: Gagal mengekstrak embedding dari {image_file.name}")
                stats["failed"] += 1
                continue
            
            # 1. Cek apakah user dengan nama tersebut sudah ada
            existing_user = users_collection.find_one({"name": person_name})
            
            # 2. Jika belum ada, insert user baru. Jika sudah, ambil id-nya
            if existing_user is None:
                # Insert user baru
                print(f"Info: Mendaftarkan user baru '{person_name}'.")
                user_result = users_collection.insert_one({
                    "name": person_name,
                    "created_at": datetime.now().isoformat()
                })
                user_id = user_result.inserted_id
            else:
                # Ambil id user yang sudah ada
                print(f"Info: User '{person_name}' sudah terdaftar, menggunakan data existing.")
                user_id = existing_user["_id"]
            
            # 3. Insert vector dengan FK user_id
            vector_document = {
                "user_id": user_id,
                "embedding": embedding.tolist(),
                "created_at": datetime.now().isoformat()
            }
            vector_collection.insert_one(vector_document)
            
            stats["success"] += 1
            stats["persons"].add(person_name)
        
        stats["persons"] = list(stats["persons"])
        
        # Refresh cache setelah registrasi selesai
        self.refresh_embeddings_cache()
        
        print(f"\n--- Hasil Registrasi ---")
        print(f"Berhasil: {stats['success']}/{stats['total_images']}")
        print(f"Gagal: {stats['failed']}/{stats['total_images']}")
        print(f"Jumlah orang terdaftar: {len(stats['persons'])}")
        print(f"Nama terdaftar: {','.join(sorted(stats['persons']))}")
        
        return stats
    
    def recognize_faces(self, image: np.ndarray, class_id: str, threshold: float = None) -> List[Dict]:
        """
        Kenali banyak wajah dalam gambar
        
        Args:
            image: Gambar dalam format BGR
            threshold: Threshold untuk recognition (default dari config)
            
        Returns:
            List of recognition results dengan user_id dan bounding box
        """
        timer_awal = time.perf_counter()
        if threshold is None:
            threshold = RECOGNITION_THRESHOLD
        
        results = []
        
        # Detect all faces with bounding boxes
        timer_deteksi_wajah = time.perf_counter()
        faces, bboxes = self.detector.detect_faces_with_boxes(image)
        print("WAKTU: Waktu deteksi wajah:", time.perf_counter() - timer_deteksi_wajah)
        
        if not faces:
            print("Warning: Tidak ada wajah terdeteksi")
            return results
        
        # Gunakan cached embeddings (sudah di-load saat startup)
        all_embeddings = self._cached_embeddings
        all_visitor_embeddings = self._cached_visitor_embeddings
        print(f"Debug: Total embeddings di cache: {len(all_embeddings)}")
        
        timer_proses_wajah = time.perf_counter()
        for i, face in enumerate(faces):
            embedding = self.encoder.get_embedding(face)
            
            if embedding is None:
                print(f"Warning: Gagal mengekstrak embedding dari wajah ke-{i+1}")
                continue
            
            # Find closest match
            print("Info: Mencari kecocokan untuk wajah ke-", i+1)
            timer_cari_cocok = time.perf_counter()
            user_id, distance = self.database.find_closest_match(embedding, all_embeddings, threshold)
            print("Debug: Jarak terdekat untuk wajah ke-", i+1, "adalah:", distance)
            print("WAKTU: Waktu cari kecocokan untuk wajah ke-", i+1, ":", time.perf_counter() - timer_cari_cocok)
            
            timer_handle_match = time.perf_counter()
            if user_id: # jika ditemukan di database users
                print(f"Info: Wajah ke-{i+1} dikenali sebagai user_id: {user_id} dengan jarak: {distance}")
                added = self.database.maybe_add_embedding(user_id, embedding, all_embeddings)
                if added:
                    # Refresh cache karena ada embedding baru
                    self.refresh_embeddings_cache()
                    all_embeddings = self._cached_embeddings
                # Get bounding box
                print("Debug: Total bounding boxes:", len(bboxes))
                bbox = bboxes[i] if i < len(bboxes) else None
                results.append({
                    "user_id": user_id,
                    "distance": distance,
                    "bounding_box": {
                        "x": int(bbox[0]) if bbox is not None else None,
                        "y": int(bbox[1]) if bbox is not None else None,
                        "width": int(bbox[2]) if bbox is not None else None,
                        "height": int(bbox[3]) if bbox is not None else None,
                        "x2": int(bbox[0] + bbox[2]) if bbox is not None else None,
                        "y2": int(bbox[1] + bbox[3]) if bbox is not None else None
                    } if bbox is not None else None
                })
                print("Info: Mencatat absensi untuk user_id:", user_id, "class_id:", class_id)
                self.database.add_user_attendance(user_id, class_id)
            else: # jika tidak ditemukan di database users
                print("Info: Wajah tidak dikenali!")
            print("WAKTU: Waktu handle kecocokan untuk wajah ke-", i+1, ":", time.perf_counter() - timer_handle_match)
        print("WAKTU: Waktu proses semua wajah:", time.perf_counter() - timer_proses_wajah)
        print("WAKTU: Waktu total pengenalan wajah banyak:", time.perf_counter() - timer_awal)
        return results
    
    def get_database_stats(self) -> Dict:
        """
        Ambil statistik database
        
        Returns:
            Dictionary dengan statistik
        """
        persons = self.database.get_unique_persons()
        
        stats = {
            "total_embeddings": self.database.get_embedding_count(),
            "total_persons": len(persons),
            "persons": {}
        }
        
        for person in persons:
            embeddings = self.database.get_embeddings_by_person(person)
            stats["persons"][person] = len(embeddings)
        
        return stats
    
    def load_image_from_base64(self, image_base64: str) -> Optional[np.ndarray]:
        """
        Load gambar dari Base64 string
        
        Args:
            image_base64: String Base64 dari gambar
            
        Returns:
            Gambar dalam format BGR (sama seperti cv2.imread) atau None jika gagal
        """
        try:
            # Decode base64 ke bytes
            image_bytes = base64.b64decode(image_base64)
            
            # Convert bytes ke numpy array
            np_array = np.frombuffer(image_bytes, dtype=np.uint8)
            
            # Decode numpy array ke image BGR (sama seperti cv2.imread)
            image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            
            if image is None:
                print("Warning: Gagal decode gambar dari base64")
                return None
            
            print(f"[DEBUG] Loaded image from base64, shape: {image.shape}")
            return image
            
        except Exception as e:
            print(f"Error: Gagal memproses base64 image: {e}")
            return None
    
    def recognize_from_base64_many(self, image_base64: str, class_id: str, threshold: float = None) -> List[Dict]:
        """
        Kenali wajah dari Base64 string
        
        Args:
            image_base64: String Base64 dari gambar
            threshold: Threshold untuk recognition
            
        Returns:
            List of recognition results
        """
        timerawal = time.perf_counter()
        image = self.load_image_from_base64(image_base64)
        print("Debug: Waktu load image dari base64:")
        timerstoptampilkantimer(timerawal)
        
        if image is None:
            return []
        return self.recognize_faces(image, class_id, threshold)
    
    def close(self):
        """
        Tutup sistem
        """
        self.database.close()
        