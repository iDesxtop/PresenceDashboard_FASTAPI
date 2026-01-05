db.Matkul.insertMany([
  {
    "nama_matkul": "Sistem Cerdas",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"), // Dr. Rani
    "class_id": ObjectId("694f3ef2825e7bcbbe801d0e"), // R. 301
    "hari": "Senin",
    "jam_awal": "07:00",
    "jam_akhir": "09:15", // 07:00 + 135 menit
    "tanggal_awal": ISODate("2026-01-26T07:00:00Z") // Senin pertama
  },
  {
    "nama_matkul": "Computer Vision",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"),
    "class_id": ObjectId("694f3f07825e7bcbbe801d10"), // R. 302
    "hari": "Selasa",
    "jam_awal": "09:30",
    "jam_akhir": "11:45", // 09:30 + 135 menit
    "tanggal_awal": ISODate("2026-01-27T09:30:00Z") // Selasa pertama
  },
  {
    "nama_matkul": "Basis Data Non Relasional",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"),
    "class_id": ObjectId("694f3f10825e7bcbbe801d12"), // R. 101
    "hari": "Rabu",
    "jam_awal": "13:00",
    "jam_akhir": "15:15", // 13:00 + 135 menit
    "tanggal_awal": ISODate("2026-01-28T13:00:00Z") // Rabu pertama
  },
  {
    "nama_matkul": "Statistika",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"),
    "class_id": ObjectId("694f3f1b825e7bcbbe801d14"), // R. 201
    "hari": "Kamis",
    "jam_awal": "15:30",
    "jam_akhir": "17:45", // 15:30 + 135 menit
    "tanggal_awal": ISODate("2026-01-29T15:30:00Z") // Kamis pertama
  }
]);