db.Matkul.insertMany([
  {
    "nama_matkul": "Sistem Cerdas",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"), 
    "class_id": ObjectId("694f3ef2825e7bcbbe801d0e"), 
    "hari": "Senin",
    "jam_awal": "07:00",
    "jam_akhir": "09:15", 
    "tanggal_awal": ISODate("2025-01-06T07:00:00Z") // 2025: 6 Jan adalah Senin
  },
  {
    "nama_matkul": "Computer Vision",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"),
    "class_id": ObjectId("694f3f07825e7bcbbe801d10"), 
    "hari": "Selasa",
    "jam_awal": "09:30",
    "jam_akhir": "11:45", 
    "tanggal_awal": ISODate("2025-01-07T09:30:00Z") // 2025: 7 Jan adalah Selasa
  },
  {
    "nama_matkul": "Basis Data Non Relasional",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"),
    "class_id": ObjectId("694f3f10825e7bcbbe801d12"), 
    "hari": "Rabu",
    "jam_awal": "13:00",
    "jam_akhir": "15:15", 
    "tanggal_awal": ISODate("2025-01-08T13:00:00Z") // 2025: 8 Jan adalah Rabu
  },
  {
    "nama_matkul": "Statistika",
    "sks": 3,
    "account_id": ObjectId("694cdd7e737cea74080c4738"),
    "class_id": ObjectId("694f3f1b825e7bcbbe801d14"), 
    "hari": "Kamis",
    "jam_awal": "15:30",
    "jam_akhir": "17:45", 
    "tanggal_awal": ISODate("2025-01-09T15:30:00Z") // 2025: 9 Jan adalah Kamis
  }
]);