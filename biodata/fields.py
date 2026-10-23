# """Definisi kolom tabel EMPMASTEREPMS.
# Format: (kolom, label, tipe, panjang_byte, wajib)
# tipe: text | textarea | date | number
# """

SECTIONS = [
    ("Identitas", [
        ("COMP_ID", "Kode Perusahaan", "text", 6, True),
        ("SITE_ID", "Kode Site", "text", 6, True),
        ("EMPCODE", "Kode Pekerja", "text", 30, True),
        ("EMPREG_ID", "No. Registrasi", "text", 30, False),
        ("EMPNAME", "Nama", "text", 50, False),
        ("OTHERNAME", "Nama Lain", "text", 50, False),
        ("BIRTH_PLACE", "Tempat Lahir", "text", 50, False),
        ("DOB", "Tanggal Lahir", "date", 0, False),
        ("SEX", "Jenis Kelamin", "text", 15, False),
        ("RELIGION", "Agama", "text", 3, False),
        ("NATIONALITY", "Kewarganegaraan", "text", 3, False),
        ("BLOOD_TYPE", "Golongan Darah", "text", 5, False),
        ("MARITALSTATUS", "Status Pernikahan", "text", 15, False),
        ("DATEMARRIED", "Tanggal Menikah", "date", 0, False),
        ("IDCARD", "No. KTP", "text", 1000, False),
        ("NO_KK", "No. KK", "text", 30, False),
        ("MONTHERNAME", "Nama Ibu Kandung", "text", 1000, False),
        ("GLASSLENS", "Kacamata", "text", 30, False),
    ]),
    ("Kepegawaian", [
        ("COMPANYBEGIN", "Mulai di Perusahaan", "date", 0, True),
        ("DATEJOIN", "Tanggal Bergabung", "date", 0, False),
        ("DATETERMINATE", "Tanggal Berhenti", "date", 0, False),
        ("TERMINATIONSTATUS", "Status Berhenti", "text", 15, False),
        ("MUTATION_SITE", "Site Mutasi", "text", 15, False),
        ("REASONSTOP", "Alasan Berhenti", "text", 15, False),
        ("EMPSTATUS", "Status Pekerja", "text", 15, False),
        ("EMPLOYEETYPE", "Tipe Pekerja", "text", 15, False),
        ("GRADE1", "Grade", "text", 15, False),
        ("ID_POSITION", "Jabatan (ID_POSITION)", "text", 15, False),
        ("JOBSPECCODE", "Kode Job Spec", "text", 30, False),
        ("REGIONAREA", "Region", "text", 15, False),
        ("DEPARTMENTCODE", "Kode Department", "text", 15, False),
        ("DIVISIONCODE", "Kode Division", "text", 15, False),
        ("PROBENDDATE", "Akhir Masa Percobaan", "date", 0, False),
        ("WORKPERMITNO", "No. Izin Kerja", "text", 15, False),
        ("WORKPERMITEXPIRYDATE", "Izin Kerja Berakhir", "date", 0, False),
        ("ACTIVE", "Aktif", "text", 2, False),
        ("INACTIVEDATE", "Tanggal Nonaktif", "date", 0, False),
        ("STATUS", "Status", "text", 100, False),
        ("EMPCODE_OLD", "Kode Pekerja Lama", "text", 30, False),
        ("STM", "STM", "text", 15, False),
        ("FLAG_HO", "Flag HO", "text", 6, False),
        ("FLAG_RICE", "Flag Beras", "text", 6, False),
        ("FLAG_PKS", "Flag PKS", "text", 6, False),
        ("SEQ_NO", "No. Urut", "text", 15, False),
        ("NATURA", "Natura", "text", 1, False),
    ]),
    ("Alamat dan Kontak", [
        ("ADDRESS", "Alamat", "text", 100, False),
        ("ADDRESS2", "Alamat 2", "text", 100, False),
        ("ADDRESS3", "Alamat 3", "text", 50, False),
        ("ZIPCODE", "Kode Pos", "text", 7, False),
        ("HOMEPHONENO", "Telepon Rumah", "text", 30, False),
        ("MOBILEPOHNENO", "No. HP", "text", 30, False),
        ("EMAILADDR", "Email", "text", 50, False),
        ("HOUSING", "Perumahan", "text", 15, False),
        ("NUMBEROFDOOR", "No. Pintu", "text", 30, False),
        ("SIM_CARD", "SIM Card", "text", 30, False),
    ]),
    ("Bank dan Jaminan Sosial", [
        ("PAYMENTMETHOD", "Metode Pembayaran", "text", 50, False),
        ("BANKNAME", "Nama Bank", "text", 50, False),
        ("BANKACCOUNTNO", "No. Rekening", "text", 30, False),
        ("BANKACCOUNTNAME", "Nama Pemilik Rekening", "text", 50, False),
        ("BASICSALARY", "Gaji Pokok", "number", 0, False),
        ("NPWP", "NPWP", "text", 30, False),
        ("NOJAMSOSTEK", "No. Jamsostek", "text", 30, False),
        ("JAMSOSTEKSTARTDATE", "Mulai Jamsostek", "date", 0, False),
        ("BPJSID", "No. BPJS", "text", 30, False),
        ("BPJSDATE", "Tanggal BPJS", "date", 0, False),
        ("LIFEINSURANCENO", "No. Asuransi Jiwa", "text", 30, False),
        ("LIFEINSURANCESTARTDATE", "Mulai Asuransi Jiwa", "date", 0, False),
        ("PENSIONPLANID", "ID Dana Pensiun", "text", 30, False),
        ("PENSIONPLANSTARTDATE", "Mulai Dana Pensiun", "date", 0, False),
        ("FAMILYSTATUSTAX", "Status Keluarga (Pajak)", "text", 4, False),
        ("FAMILYSTATUSRICE", "Status Keluarga (Beras)", "text", 4, False),
        ("FAMILYSTATUSJAMSOSTEK", "Status Keluarga (Jamsostek)", "text", 100, False),
    ]),
    ("Lain-lain", [
        ("FINGERID", "ID Fingerprint", "text", 30, False),
        ("FINGERTYPE", "Tipe Fingerprint", "text", 15, False),
        ("FINGERSCH", "Jadwal Fingerprint", "text", 15, False),
        ("KOPERASI", "Koperasi", "text", 100, False),
        ("REMARKS", "Catatan", "textarea", 4000, False),
    ]),
]

FIELDS = [f for _, fields in SECTIONS for f in fields]
AUDIT = ["INPUTBY", "INPUTDATE", "UPDATEBY", "UPDATEDATE"]

# Kolom untuk halaman daftar
LIST_COLUMNS = ["EMPCODE", "EMPNAME", "DEPARTMENTCODE", "EMPSTATUS", "ACTIVE"]

# Hanya terlihat oleh superuser sampai fitur role (Tahap 3) dibuat
SENSITIVE = {"BASICSALARY", "NPWP", "IDCARD", "BANKACCOUNTNO",
             "BANKACCOUNTNAME", "NO_KK", "NOJAMSOSTEK", "BPJSID",
             "LIFEINSURANCENO"}
