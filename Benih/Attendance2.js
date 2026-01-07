// 1. Daftar ID Mahasiswa (9 Orang)
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

// 2. Daftar Mata Kuliah (Config Jadwal Awal 2025)
var courses = [
  {
    name: "Sistem Cerdas",
    id_spesial: ObjectId("696cdef27563f8ba7000b111"),
    // Senin, 6 Jan 2025, 07:00
    startDate: new Date("2026-04-21T10:00:00.000+00:00") 
  },
  {
    name: "Computer Vision",
    class_id: ObjectId("694f3f07825e7bcbbe801d10"),
    // Selasa, 7 Jan 2025, 09:30
    startDate: new Date("2025-01-07T09:30:00Z")
  },
  {
    name: "Basis Data Non Relasional",
    class_id: ObjectId("694f3f10825e7bcbbe801d12"),
    // Rabu, 8 Jan 2025, 13:00
    startDate: new Date("2025-01-08T13:00:00Z")
  },
  {
    name: "Statistika",
    class_id: ObjectId("694f3f1b825e7bcbbe801d14"),
    // Kamis, 9 Jan 2025, 15:30
    startDate: new Date("2025-01-09T15:30:00Z")
  }
];

// --- KONFIGURASI UMUM ---
var totalMeetings = 15;      // Jumlah pertemuan per matkul
var attendanceRate = 0.85;   // Peluang masuk (0.85 = 85%)
var maxLateMinutes = 20;     // Max telat 20 menit

var attendanceData = [];

// 3. Proses Looping (3 Layer: Course -> Student -> Meetings)
courses.forEach(function(course) {
    
    print("Generating data for: " + course.name + "..."); // Opsional: log progress

    studentIds.forEach(function(studentId) {
        
        for (var i = 0; i < totalMeetings; i++) {
            
            // Random Check: Masuk atau Bolos?
            if (Math.random() < attendanceRate) {
                
                // Hitung tanggal pertemuan minggu ke-i
                var baseDate = new Date(course.startDate.getTime() + (i * 7 * 24 * 60 * 60 * 1000));
                
                // Tambahkan variasi menit (Jitter)
                var randomDelay = Math.floor(Math.random() * maxLateMinutes * 60 * 1000);
                var actualTime = new Date(baseDate.getTime() + randomDelay);

                attendanceData.push({
                    "user_id": studentId,
                    "class_id": course.class_id,
                    "timestamp": actualTime.toISOString() // Format String ISO
                });
            }
        }
    });
});

// 4. Eksekusi Insert
db.Attendance.insertMany(attendanceData);