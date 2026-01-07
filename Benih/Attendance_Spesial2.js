// 1. Daftar ID Mahasiswa
var studentIds = [
  ObjectId("695b8c2b540a02b5137daea6"), // Bayu
  ObjectId("695b8c30540a02b5137daeb1"), // Danes
  ObjectId("695b8c31540a02b5137daeb7"), // Faisal
  ObjectId("695b8c33540a02b5137daebe"), // Ichsan
  ObjectId("695b8c34540a02b5137daec7"), // Marco
  ObjectId("695b8c36540a02b5137daed0"), // Rauf
  ObjectId("695b8c37540a02b5137daed8"), // Yoga
  ObjectId("695b8c39540a02b5137daee0"), // Yusuf
  ObjectId("695b8c3b540a02b5137daee8")  // Zaki
];

// 2. Daftar Kelas Spesial (ID dan Waktu Dasar sesuai data insert Anda)
var specialClasses = [
  {
    // Sistem Cerdas - Pertemuan 16
    spesial_id: ObjectId("696cdef27563f8ba7000b111"), 
    baseDate: new Date("2026-04-21T10:00:00.000Z")
  },
  {
    // Computer Vision - Pertemuan 16
    spesial_id: ObjectId("696cdef27563f8ba7000b112"), 
    baseDate: new Date("2026-04-22T13:00:00.000Z")
  },
  {
    // BDNR - Pertemuan 16
    spesial_id: ObjectId("696cdef27563f8ba7000b113"), 
    baseDate: new Date("2026-04-23T08:00:00.000Z")
  },
  {
    // Statistika - Pertemuan 16
    spesial_id: ObjectId("696cdef27563f8ba7000b114"), 
    baseDate: new Date("2026-04-24T10:00:00.000Z")
  }
];

// --- KONFIGURASI ---
var attendanceRate = 0.85; // 85% Hadir
var maxLateMinutes = 20;   // Maksimal telat 20 menit

var attendanceSpecialData = [];

// 3. Proses Looping (Kelas Spesial -> Mahasiswa)
specialClasses.forEach(function(cls) {
    
    studentIds.forEach(function(studentId) {
        
        // Random Check: Apakah masuk?
        if (Math.random() < attendanceRate) {
            
            // Hitung waktu masuk dengan jitter (variasi menit)
            var randomDelay = Math.floor(Math.random() * maxLateMinutes * 60 * 1000);
            var actualTime = new Date(cls.baseDate.getTime() + randomDelay);

            attendanceSpecialData.push({
                "user_id": studentId,
                "spesial_id": cls.spesial_id,
                // Disimpan sebagai Date Object (akan menjadi ISODate di Mongo)
                "timestamp": actualTime.toISOString()
            });
        }
    });
});

// 4. Eksekusi Insert
db.Attendance_Spesial.insertMany(attendanceSpecialData);