from . import oracle_db

# === Nama tabel (dari .env lewat oracle_db) ===
TABLE = oracle_db.TABLE
TABLE_TAX = oracle_db.TABLE_TAXSTATUS
TABLE_KARIER = oracle_db.TABLE_KARIER
TABLE_JOBSPEC = oracle_db.TABLE_JOBSPEC
TABLE_MUTASI = oracle_db.TABLE_MUTASI
# === End Nama Tabel ===

PER_PAGE = 25

# === Pagar data Comp/Site ===
SCOPE_WHERE = "COMP_ID = :c AND SITE_ID = :s"
KEY_WHERE = SCOPE_WHERE + " AND EMPCODE = :e"
TAX_KEY_WHERE = "COMP_ID = :c AND SITE_ID = :s AND NIK_STAFF = :e"
NIK_WHERE = TAX_KEY_WHERE
# === End Pagar data Comp/Site ===


# === Biodata ===
LOCKED = ('COMP_ID', 'SITE_ID')       

# Kolom lama di biodata yang kini hanya diubah lewat tab riwayat.
DIKUNCI_PAJAK = ('FAMILYSTATUSTAX', 
                 'FAMILYSTATUSRICE',
                 'ID_POSITION', 
                 'DEPARTMENTCODE', 
                 'JOBSPECCODE')
TAB_KUNCI = {
    'FAMILYSTATUSTAX': 'Tax Status', 
    'FAMILYSTATUSRICE': 'Tax Status',
    'ID_POSITION': 'Riwayat Karir', 
    'DEPARTMENTCODE': 'Riwayat Karir',
    'JOBSPECCODE': 'Riwayat Karir',
}
# === End Biodata ===

# === Riwayat Karir ===
KARIER_TEKS = [('ID_POSITION', 'Jabatan (ID Position)'),
               ('DEPT_ID', 'Department'),
               ('UNIT_ID', 'Unit')]
KARIER_BOLEH_MASA_DEPAN = True
# === End Riwayat Karir ===

# === Mutasi dan Termination ===
MUTASI_FROM = (f"{TABLE_MUTASI} t LEFT JOIN {TABLE} e "
               f"ON e.COMP_ID = t.COMP_ID AND e.SITE_ID = t.SITE_ID "
               f"AND e.EMPCODE = t.NIK_STAFF")
# === End Mutasi dan Termination ===