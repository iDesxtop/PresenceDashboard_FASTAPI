db.attendance.insertMany([
  // ==========================================
  // 1. SISTEM CERDAS (Senin, 26 Jan 2026, 07:00)
  // ID Matkul: ...445
  // ==========================================
  {
    "user_id": ObjectId("695b8c2b540a02b5137daea6"), // Bayu
    "timestamp": "2026-01-26 06:55:12",
    "class_id": ObjectId("695b8b477afa3aa72dc31445"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c30540a02b5137daeb1"), // Danes
    "timestamp": "2026-01-26 06:58:45",
    "class_id": ObjectId("695b8b477afa3aa72dc31445"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c31540a02b5137daeb7"), // Faisal
    "timestamp": "2026-01-26 07:00:05",
    "class_id": ObjectId("695b8b477afa3aa72dc31445"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c33540a02b5137daebe"), // Ichsan (Manual - Misal telat & masuk via admin)
    "timestamp": "2026-01-26 07:15:00",
    "class_id": ObjectId("695b8b477afa3aa72dc31445"),
    "status": "Manual"
  },
  {
    "user_id": ObjectId("695b8c34540a02b5137daec7"), // Marco
    "timestamp": "2026-01-26 06:59:30",
    "class_id": ObjectId("695b8b477afa3aa72dc31445"),
    "status": "Otomatis"
  },

  // ==========================================
  // 2. COMPUTER VISION (Selasa, 27 Jan 2026, 09:30)
  // ID Matkul: ...446
  // ==========================================
  {
    "user_id": ObjectId("695b8c36540a02b5137daed0"), // Rauf
    "timestamp": "2026-01-27 09:25:10",
    "class_id": ObjectId("695b8b477afa3aa72dc31446"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c37540a02b5137daed8"), // Yoga
    "timestamp": "2026-01-27 09:28:55",
    "class_id": ObjectId("695b8b477afa3aa72dc31446"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c39540a02b5137daee0"), // Yusuf
    "timestamp": "2026-01-27 09:30:02",
    "class_id": ObjectId("695b8b477afa3aa72dc31446"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c3b540a02b5137daee8"), // Zaki
    "timestamp": "2026-01-27 09:35:20",
    "class_id": ObjectId("695b8b477afa3aa72dc31446"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c2b540a02b5137daea6"), // Bayu (Hadir lagi di matkul ini)
    "timestamp": "2026-01-27 09:20:15",
    "class_id": ObjectId("695b8b477afa3aa72dc31446"),
    "status": "Otomatis"
  },

  // ==========================================
  // 3. BASIS DATA NO-SQL (Rabu, 28 Jan 2026, 13:00)
  // ID Matkul: ...447
  // ==========================================
  {
    "user_id": ObjectId("695b8c30540a02b5137daeb1"), // Danes
    "timestamp": "2026-01-28 12:55:40",
    "class_id": ObjectId("695b8b477afa3aa72dc31447"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c31540a02b5137daeb7"), // Faisal (Manual - Wajah tidak terdeteksi)
    "timestamp": "2026-01-28 13:05:10",
    "class_id": ObjectId("695b8b477afa3aa72dc31447"),
    "status": "Manual"
  },
  {
    "user_id": ObjectId("695b8c33540a02b5137daebe"), // Ichsan
    "timestamp": "2026-01-28 12:59:59",
    "class_id": ObjectId("695b8b477afa3aa72dc31447"),
    "status": "Otomatis"
  },

  // ==========================================
  // 4. STATISTIKA (Kamis, 29 Jan 2026, 15:30)
  // ID Matkul: ...448
  // ==========================================
  {
    "user_id": ObjectId("695b8c34540a02b5137daec7"), // Marco
    "timestamp": "2026-01-29 15:25:33",
    "class_id": ObjectId("695b8b477afa3aa72dc31448"),
    "status": "Otomatis"
  },
  {
    "user_id": ObjectId("695b8c36540a02b5137daed0"), // Rauf
    "timestamp": "2026-01-29 15:32:10",
    "class_id": ObjectId("695b8b477afa3aa72dc31448"),
    "status": "Otomatis"
  }
]);