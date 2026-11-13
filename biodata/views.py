import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import quote

import cx_Oracle
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from . import oracle_db
from .fields import (AUDIT, FIELDS, JENIS_TRANSAKSI, KODE_BERAS, KODE_MUTASI, KODE_PAJAK, LIST_COLUMNS, SECTIONS, SENSITIVE)
from .forms import CompSiteLoginForm, _ambil_pasangan

TABLE = oracle_db.TABLE
PER_PAGE = 25
SCOPE_WHERE = "COMP_ID = :c AND SITE_ID = :s"
KEY_WHERE = SCOPE_WHERE + " AND EMPCODE = :e"
LOCKED = ('COMP_ID', 'SITE_ID') # selalu dari login, tidak ada di form
TABLE_TAX = oracle_db.TABLE_TAXSTATUS
TAX_KEY_WHERE = "COMP_ID = :c AND SITE_ID = :s AND NIK_STAFF = :e"
# Kolom lama di biodata yang kini hanya diubah lewat riwayat Tax Status.
# Untuk membatalkan penguncian, ganti menjadi tuple kosong: ()
DIKUNCI_PAJAK = ('FAMILYSTATUSTAX', 'FAMILYSTATUSRICE', 'ID_POSITION', 'DEPARTMENTCODE', 'JOBSPECCODE')

# Tab tempat tiap kolom terkunci diubah (untuk petunjuk di form)
TAB_KUNCI = {
    'FAMILYSTATUSTAX': 'Tax Status', 
    'FAMILYSTATUSRICE': 'Tax Status',
    'ID_POSITION': 'Riwayat Karir',
    'DEPARTMENTCODE': 'Riwayat Karir',
    'JOBSPECCODE': 'Riwayat Karir',
}

TABLE_KARIER = oracle_db.TABLE_KARIER
TABLE_JOBSPEC = oracle_db.TABLE_JOBSPEC
NIK_WHERE = TAX_KEY_WHERE # Comp + Site + NIK, dipakai tabel riwayat
KARIER_TEKS = [('ID_POSITION', 'Jabatan (ID POSITION)'),
               ('DEPT_ID', 'Department'),
               ('UNIT_ID', 'Unit')]
KARIER_BOLEH_MASA_DEPAN = True 
TABLE_MUTASI = oracle_db.TABLE_MUTASI
MUTASI_FROM = (f"{TABLE_MUTASI} t LEFT JOIN {TABLE} e"
               f"ON e.COMP_ID = t.COMP_ID AND e.SITE_ID = t.SITE_ID "
               f"AND e.EMPCODE = t.NIK_STAFF")


# redirect(request.path) membuka kembali halaman yang sama lewat GET, sehingga form dimuat dengan token baru. Isian yang tadi diketik memang hilang, tetapi pesannya menjelaskan alasannya.
def csrf_gagal(request, reason=''):
    """Dipanggil Django saat token CSRF usang atau hilang."""
    messages.error(
        request,
        'Halaman sudah kedaluwarsa (biasanya karena login atau logout di '
        'tab lain). Silakan coba lagi.')
    return redirect(request.path)

# === LOGIN & AKSES & CRSF ===

class CompSiteLoginView(LoginView):
    authentication_form = CompSiteLoginForm
    
    def form_valid(self, form):
        response = super().form_valid(form)
        comp = form.cleaned_data['comp_id']
        site = form.cleaned_data['site_id']
        nama_comp, nama_site, = form.nama(comp, site)
        # ID dipakai untuk filter query, nama hanya untuk tampilan
        self.request.session['comp_id'] = comp
        self.request.session['site_id'] = site
        self.request.session['comp_name'] = nama_comp
        self.request.session['site_name'] = nama_site
        return response
     
def comp_site_required(view):
    # Wajib login DAN punya Comp/Site di session.
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('comp_id') or not request.session.get('site_id'):
            logout(request)
            return redirect('login')
        return view(request, *args, **kwargs)
    return wrapper

def csrf_gagal(request, reason=''):
    # Dipanggil Django saat token CSRF usang atau hilang.
    messages.error(
        request,
        'Halaman sudah kedaluwarsa Silahkan login ulang kembali'
    ) 
    return redirect(request.path)

# mengambil Comp/Site dari session. Semua query memakainya.
def _scope(request):
    return request.session['comp_id'], request.session['site_id']    

# === END LOGIN & AKSES ===

# Fungsi Bantu
def _boleh_sensitif(user):
    return user.has_perm('biodata.lihat_sensitif')

def _kolom_aktif(user, mode):
    #"""Kolom yang tampil di form DAN boleh disimpan oleh user ini."""
    hasil = []
    for f in FIELDS:
        col = f[0]
        if col in LOCKED or col in DIKUNCI_PAJAK:
            continue
        if mode == 'ubah' and col == 'EMPCODE':
            continue
        if col in SENSITIVE and not _boleh_sensitif(user):
            continue
        hasil.append(f)
    return hasil

def _ke_input(value, tipe):
    #"""Ubah nilai dari Oracle menjadi teks untuk kolom isian."""
    if value is None:
        return ''
    if tipe == 'date':
        return value.strftime('%Y-%m-%d')
    if tipe == 'number':
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
    return str(value)

def _tampil(value):
    if isinstance(value, datetime):
        return value.strftime('%d-%m-%Y %H:%M')
    return '' if value is None else value


def _parse(field, raw):
    """Kembalikan (nilai_untuk_oracle, pesan_error)."""
    col, label, tipe, length, required = field
    raw = (raw or '').strip()
    if not raw:
        return None, ('Wajib diisi' if required else None)
    if tipe == 'date':
        try:
            return datetime.strptime(raw, '%Y-%m-%d'), None
        except ValueError:
            return None, 'Tanggal tidak valid'
    if tipe == 'number':
        try:
            return Decimal(raw.replace(',', '.')), None
        except InvalidOperation:
            return None, 'Angka tidak valid'
    if len(raw.encode('utf-8')) > length:
        return None, f'Maksimal {length} karakter'
    return raw, None


def _kumpulkan(request, aktif):
    """Baca dan validasi isian POST. Hasil: (isian_mentah, nilai_valid, error)."""
    raw = {f[0]: request.POST.get(f[0], '') for f in aktif}
    parsed, errors = {}, {}
    for f in aktif:
        nilai, err = _parse(f, raw[f[0]])
        if err:
            errors[f[0]] = err
        else:
            parsed[f[0]] = nilai
    return raw, parsed, errors


def _form_sections(aktif, values, errors, terkunci=()):
    """Susun data form per bagian. Kolom 'terkunci' tampil tapi tidak bisa diubah."""
    nama_aktif = {f[0] for f in aktif}
    hasil = []
    for title, fields in SECTIONS:
        items = [
            {'name': col, 'label': label, 'type': tipe, 'length': length,
             'req': req, 'value': values.get(col, ''),
             'error': errors.get(col), 'locked': col in terkunci,
             'hint': TAB_KUNCI.get(col, '')}
            for col, label, tipe, length, req in fields
            if col in nama_aktif or col in terkunci
        ]
        if items:
            hasil.append({'title': title, 'fields': items})
    return hasil


# === Halaman HOME ===
@comp_site_required
def home(request):
    return render(request, 'biodata/home.html')

# Lihat Data
@comp_site_required
def biodata_list(request):
    comp, site = _scope(request)
    q = request.GET.get('q', '').strip()
    try:
        page = max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        page = 1

    where = f"WHERE {SCOPE_WHERE}"
    binds = {'c': comp, 's': site}
    if q:
        # tanda kurung wajib agar OR tidak mengalahkan filter comp/site
        where += " AND (UPPER(EMPCODE) LIKE :q OR UPPER(EMPNAME) LIKE :q)"
        binds['q'] = '%' + q.upper() + '%'

    total = oracle_db.scalar(f"SELECT COUNT(*) FROM {TABLE} {where}", binds)
    pages = max(math.ceil(total / PER_PAGE), 1)
    page = min(page, pages)

    cols = ", ".join(LIST_COLUMNS)
    # ROWNUM dipakai karena Oracle 11.2 belum mendukung OFFSET/FETCH
    sql = (
        f"SELECT * FROM ("
        f" SELECT a.*, ROWNUM rn FROM ("
        f"  SELECT {cols} FROM {TABLE} {where}"
        f"  ORDER BY COMP_ID, SITE_ID, EMPCODE) a"
        f" WHERE ROWNUM <= :hi) WHERE rn > :lo"
    )
    rows = oracle_db.fetch_all(sql, dict(binds, hi=page * PER_PAGE,
                                         lo=(page - 1) * PER_PAGE))
    return render(request, 'biodata/list.html', {
        'rows': rows, 'q': q, 'page': page, 'pages': pages, 'total': total,
        'prev': page - 1, 'next': page + 1,
    })

# Lihat Data secara keseluruhan
@comp_site_required
def biodata_edit(request):
    """Terbuka hanya-baca; user berizin dapat menekan Ubah lalu Simpan."""
    comp, site = _scope(request)
    kode = request.GET.get('code', '')
    key = {'c': comp, 's': site, 'e': kode}
    bisa_ubah = request.user.has_perm('biodata.ubah_biodata')
    aktif = _kolom_aktif(request.user, 'ubah')

    kolom = [f[0] for f in aktif] + ['EMPCODE'] + list(DIKUNCI_PAJAK) + AUDIT
    row = oracle_db.fetch_one(
        f"SELECT {', '.join(kolom)} FROM {TABLE} WHERE {KEY_WHERE}", key)
    if not row:
        raise Http404("Data tidak ditemukan")

    raw, errors = {}, {}
    if request.method == 'POST':
        if not bisa_ubah:
            raise PermissionDenied
        raw, parsed, errors = _kumpulkan(request, aktif)

        if not errors:
            sets = [f"{col} = :b{i}" for i, col in enumerate(parsed)]
            binds = dict(key)
            binds.update({f'b{i}': v for i, v in enumerate(parsed.values())})
            binds['updby'] = request.user.username[:30]
            sql = (f"UPDATE {TABLE} SET {', '.join(sets)}, "
                   f"UPDATEBY = :updby, UPDATEDATE = SYSDATE "
                   f"WHERE {KEY_WHERE}")
            try:
                jumlah = oracle_db.execute(sql, binds)
            except cx_Oracle.DatabaseError as exc:
                messages.error(request, f'Gagal menyimpan ke Oracle: {exc}')
            else:
                if jumlah == 1:
                    messages.success(request, 'Perubahan berhasil disimpan.')
                    return redirect(f"{reverse('biodata:edit')}?code={quote(kode)}")
                messages.error(request,
                               'Data tidak ditemukan, tidak ada yang diubah.')
        else:
            messages.error(request, 'Periksa kembali isian yang bertanda merah.')
    else:
        raw = {f[0]: _ke_input(row.get(f[0]), f[2]) for f in aktif}

    tampil = dict(raw, EMPCODE=row['EMPCODE'])
    for c in DIKUNCI_PAJAK:
        tampil[c] = row.get(c) or ''
    return render(request, 'biodata/form.html', {
        'mode': 'ubah',
        'judul': f"{row['EMPCODE']} - {row.get('EMPNAME') or ''}",
        'kode_pekerja': row['EMPCODE'],
        'sections': _form_sections(aktif, tampil, errors, terkunci=('EMPCODE',) + DIKUNCI_PAJAK),
        'bisa_ubah': bisa_ubah,
        'edit_aktif': request.method == 'POST',
        'audit': [(c, _tampil(row[c])) for c in AUDIT],
    })

@comp_site_required
@permission_required('biodata.tambah_biodata', raise_exception=True)
def biodata_create(request):
    comp, site = _scope(request)
    aktif = _kolom_aktif(request.user, 'tambah')
    raw, errors = {}, {}

    if request.method == 'POST':
        raw, parsed, errors = _kumpulkan(request, aktif)

        if not errors:
            key = {'c': comp, 's': site, 'e': parsed['EMPCODE']}
            ada = oracle_db.scalar(
                f"SELECT COUNT(*) FROM {TABLE} WHERE {KEY_WHERE}", key)
            if ada:
                errors['EMPCODE'] = ('Kode Pekerja ini sudah ada '
                                     'di Comp dan Site yang sedang dipakai')

        if not errors:
            parsed['COMP_ID'] = comp          # selalu dari login
            parsed['SITE_ID'] = site
            cols = [c for c, v in parsed.items() if v is not None]
            binds = {f'b{i}': parsed[c] for i, c in enumerate(cols)}
            placeholders = [f':b{i}' for i in range(len(cols))]
            binds['inputby'] = request.user.username[:30]
            sql = (f"INSERT INTO {TABLE} ({', '.join(cols)}, INPUTBY, INPUTDATE) "
                   f"VALUES ({', '.join(placeholders)}, :inputby, SYSDATE)")
            try:
                oracle_db.execute(sql, binds)
            except cx_Oracle.IntegrityError:
                errors['EMPCODE'] = 'Data dengan kunci ini sudah ada'
            except cx_Oracle.DatabaseError as exc:
                messages.error(request, f'Gagal menyimpan ke Oracle: {exc}')
            else:
                messages.success(request, 'Data berhasil ditambahkan.')
                return redirect(
                    f"{reverse('biodata:edit')}?code={quote(parsed['EMPCODE'])}")

        if errors:
            messages.error(request, 'Periksa kembali isian yang bertanda merah.')

    return render(request, 'biodata/form.html', {
        'mode': 'tambah',
        'judul': 'Tambah Biodata',
        'sections': _form_sections(aktif, raw, errors),
        'bisa_ubah': False,
        'edit_aktif': True,
    })

@comp_site_required
def taxstatus(request):
    """Riwayat status pajak dan beras satu pekerja. Hanya lihat dan tambah."""
    comp, site = _scope(request)
    key = {'c': comp, 's': site, 'e': request.GET.get('code', '')}
    
    # Pekerja harus ada di biodata untuk Comp/Site ini
    pekerja = oracle_db.fetch_one(
        f"SELECT EMPCODE, EMPNAME FROM {TABLE} WHERE {KEY_WHERE}" , key
    )
    if not pekerja:
        raise Http404("Data tidak ditemukan")
    key['e'] = pekerja['EMPCODE']
    
    bisa_tambah = request.user.has_perm('biodata.tambah_taxstatus')
    raw, errors = {}, {}
    
    if request.method == 'POST':
        if not bisa_tambah:
            raise PermissionDenied
        raw = {'TAX_STAT_ID': request.POST.get('TAX_STAT_ID', '').strip(),
               'RICE_STAT_ID': request.POST.get('RICE_STAT_ID', '').strip()}
        if raw['TAX_STAT_ID'] not in KODE_PAJAK:
            errors['TAX_STAT_ID'] = 'Pilih status pajak dari daftar'
        if raw['RICE_STAT_ID'] not in KODE_BERAS:
            errors['RICE_STAT_ID'] = 'Pilih status beras dari daftar'


        if errors:
            messages.error(request, 'Periksa kembali isian yang bertanda merah.')
        else:
            # tanggal berlaku selalu hari ini: tidak boleh maju, tidak boleh mundur
            sudah = oracle_db.scalar(
                f"SELECT COUNT(*) FROM {TABLE_TAX} "
                f"WHERE {TAX_KEY_WHERE} AND DATETS >= TRUNC(SYSDATE)", key)
            if sudah:
                messages.error(
                    request,
                    'Pekerja ini sudah punya status bertanggal hari ini atau '
                    'sesudahnya, jadi tidak bisa ditambah lagi.')
            else:
                sql = (f"INSERT INTO {TABLE_TAX} "
                       f"(COMP_ID, SITE_ID, NIK_STAFF, DATETS, TAX_STAT_ID, "
                       f"RICE_STAT_ID, INPUTBY, INPUTDATE) "
                       f"VALUES (:c, :s, :e, TRUNC(SYSDATE), :tax, :rice, "
                       f":inputby, SYSDATE)")
                binds = dict(key, tax=raw['TAX_STAT_ID'],
                             rice=raw['RICE_STAT_ID'],
                             inputby=request.user.username[:30])
                try:
                    oracle_db.execute(sql, binds)
                except cx_Oracle.IntegrityError:
                    messages.error(request, 'Status untuk tanggal ini sudah ada.')
                except cx_Oracle.DatabaseError as exc:
                    messages.error(request, f'Gagal menyimpan ke Oracle: {exc}')
                else:
                    messages.success(request, 'Status baru berhasil ditambahkan.')
                    return redirect(
                        f"{reverse('biodata:taxstatus')}?code={quote(pekerja['EMPCODE'])}")

    sql = (
        f"SELECT t.DATETS, t.TAX_STAT_ID, t.RICE_STAT_ID, t.INPUTBY, t.INPUTDATE, "
        f"CASE WHEN t.DATETS = (SELECT MAX(x.DATETS) FROM {TABLE_TAX} x "
        f"WHERE x.COMP_ID = t.COMP_ID AND x.SITE_ID = t.SITE_ID "
        f"AND x.NIK_STAFF = t.NIK_STAFF AND x.DATETS <= SYSDATE) "
        f"THEN 1 ELSE 0 END AS BERLAKU "
        f"FROM {TABLE_TAX} t "
        f"WHERE t.COMP_ID = :c AND t.SITE_ID = :s AND t.NIK_STAFF = :e "
        f"ORDER BY t.DATETS DESC"
    )
    riwayat = oracle_db.fetch_all(sql, key)
    for r in riwayat:
        r['TGL'] = r['DATETS'].strftime('%d-%m-%Y') if r['DATETS'] else ''
        r['WAKTU_INPUT'] = _tampil(r['INPUTDATE'])

    return render(request, 'biodata/taxstatus.html', {
        'pekerja': pekerja, 'riwayat': riwayat,
        'bisa_tambah': bisa_tambah,
        'kode_pajak': KODE_PAJAK, 'kode_beras': KODE_BERAS,
        'raw': raw, 'errors': errors,
    })
    
@comp_site_required
def karier(request):
    """Riwayat karir satu pekerja. Hanya lihat dan tambah."""
    comp, site = _scope(request)
    key = {'c': comp, 's':site, 'e': request.GET.get('code', '')}
    
    # pekerja harus ada di biodata untuk comp/site ini
    pekerja = oracle_db.fetch_one(
        f"SELECT EMPCODE, EMPNAME FROM {TABLE} WHERE {KEY_WHERE}", key)
    if not pekerja:
        raise Http404("Data tidak ditemukan")
    key['e'] = pekerja['EMPCODE']
    
    # daftar job spec milik Comp/Site ini (untuk pilihan & validasi)
    jobspec = oracle_db.fetch_all(
        f"SELECT JOBSPECCODE, DESCRIPTION FROM {TABLE_JOBSPEC} "
        f"WHERE COMP_ID = :c AND SITE_ID = :s ORDER BY JOBSPECCODE",
        {'c': comp, 's': site}) 
    deskripsi = {j['JOBSPECCODE']: j['DESCRIPTION'] or '' for j in jobspec}
    
    bisa_tambah = request.user.has_perm('biodata.tambah_karier')
    raw, errors = {}, {}
    
    if request.method == 'POST':
        if not bisa_tambah:
            raise PermissionDenied
        nama_kolom = ['TGL_AWAL', 'ID_POSITION', 'DEPT_ID', 'UNIT_ID', 'JOB_SPEC']
        raw = {k: request.POST.get(k, '').strip() for k in nama_kolom}
        
        for col in ('ID_POSITION', 'DEPT_ID', 'UNIT_ID', 'JOB_SPEC'):
            if not raw[col]:
                errors[col] = 'Waji diisi'
            elif len(raw[col].encode('utf-8')) > 15:
                errors[col] = 'Maksimal 15 karakter'
        # bila daftar job spec ada, kode harus salah satu darinya
        if 'JOB_SPEC' not in errors and deskripsi and raw['JOB_SPEC'] not in deskripsi:
            errors['JOB_SPEC'] = 'Pilih Job Spec dari daftar'
        
        tgl = None
        if not raw['TGL_AWAL']:
            errors['TGL_AWAL'] = 'Wajib diisi'
        else:
            try:
                tgl = datetime.strptime(raw['TGL_AWAL'], '%Y-%m-%d')
            except ValueError:
                errors['TGL_AWAL'] = 'Tanggal tidak valid'
        
        if tgl and 'TGL_AWAL' not in errors:
            terakhir = oracle_db.scalar(
                f"SELECT MAX(TRUNC(TGL_AWAL)) FROM {TABLE_KARIER} "
                f"WHERE {NIK_WHERE}", key)
            if terakhir and tgl <= terakhir:
                errors['TGL_AWAL'] = (
                    f"Harus lebih baru dari {terakhir.strftime('%d-%m-%Y')} "
                    f"(tanggal mulai terakhir pekerja ini)")
            elif not KARIER_BOLEH_MASA_DEPAN:
                hari_ini = oracle_db.scalar("SELECT TRUNC(SYSDATE) FROM DUAL")
                if tgl > hari_ini:
                    errors['TGL_AWAL'] = 'Tanggal tidak boleh di masa depan'
                    
        if errors:
            messages.error(request, 'Periksa kembali isian yang bertanda merah.')
        else:
            sql = (f"INSERT INTO {TABLE_KARIER} "
                   f"(COMP_ID, SITE_ID, NIK_STAFF, TGL_AWAL, ID_POSITION, "
                   f"DEPT_ID, UNIT_ID, JOB_SPEC, INPUTBY, INPUTDATE) "
                   f"VALUES (:c, :s, :e, :tgl, :pos, :dept, :unit, :job, "
                   f":inputby, SYSDATE")
            binds = dict(key, tgl=tgl, pos=raw['ID_POSITION'],
                         dept=raw['DEPT_ID'], unit=raw['UNIT_ID'],
                         job=raw['JOB_SPEC'],
                         inputby=request.user.username[:30])
            try:
                oracle_db.execute(sql, binds)
            except cx_Oracle.IntegrityError:
                messages.error(request, 'Riwayat untuk tanggal ini sudah ada.')
            except cx_Oracle.DatabaseError as exc:
                messages.error(request, f'Gagal menyimpan ke oracle: {exc}')
            else:
                messages.success(request, 'Riwayat karir berhasil ditambahkan.')
                return redirect(
                    f"{reverse('biodata:karier')}?code={quote(pekerja['EMPCODE'])}")
                
    sql = (
        f"SELECT t.TGL_AWAL, t.ID_POSITION, t.DEPT_ID, t.UNIT_ID, t.JOB_SPEC, "
        f"t.INPUTBY, t.INPUTDATE, "
        f"CASE WHEN t.TGL_AWAL = (SELECT MAX(x.TGL_AWAL) FROM {TABLE_KARIER} x "
        f"WHERE x.COMP_ID = t.COMP_ID AND x.SITE_ID = t.SITE_ID "
        f"AND x.NIK_STAFF = t.NIK_STAFF AND x.TGL_AWAL <= SYSDATE) "
        f"THEN 1 ELSE 0 END AS BERLAKU "
        f"FROM {TABLE_KARIER} t "
        f"WHERE t.COMP_ID = :c AND t.SITE_ID = :s AND t.NIK_STAFF = :e "
        f"ORDER BY t.TGL_AWAL DESC"
    )
    riwayat = oracle_db.fetch_all(sql, key)
    for r in riwayat:
        r['TGL'] = r['TGL_AWAL'].strftime('%d-%m-%Y') if r['TGL_AWAL'] else ''
        r['JOB_DESC'] = deskripsi.get(r['JOB_SPEC'], '')
        r['WAKTU_INPUT'] = _tampil(r['INPUTDATE'])
    
    kolom_teks = [{'name': c, 'label': l, 'value': raw.get(c, ''),
                   'error': errors.get(c)} for c, l in KARIER_TEKS]
    return render(request, 'biodata/karier.html', {
        'pekerja': pekerja, 'riwayat': riwayat, 'bisa_tambah': bisa_tambah,
        'jobspec': jobspec, 'kolom_teks': kolom_teks, 'raw': raw,
        'errors': errors,
    })
    
def _daftar_site(comp):
    """[[site_id, nama_site], ...] untuk perusahaan ini, dari VW_REF_COMPSITE."""
    try:
        return _ambil_pasangan().get(comp, {}).get('sites', [])
    except Exception:
        return []


@comp_site_required
@permission_required('biodata.lihat_mutasi', raise_exception=True)
def mutasi_list(request):
    comp, site = _scope(request)
    konteks = {'belum_siap': not TABLE_MUTASI, 'rows': [], 'q': '',
               'page': 1, 'pages': 1, 'total': 0, 'prev': 0, 'next': 2}
    if not TABLE_MUTASI:
        return render(request, 'biodata/mutasi_list.html', konteks)

    q = request.GET.get('q', '').strip()
    try:
        page = max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        page = 1

    where = "WHERE t.COMP_ID = :c AND t.SITE_ID = :s"
    binds = {'c': comp, 's': site}
    if q:
        # tanda kurung wajib agar OR tidak mengalahkan filter comp/site
        where += " AND (UPPER(t.NIK_STAFF) LIKE :q OR UPPER(e.EMPNAME) LIKE :q)"
        binds['q'] = '%' + q.upper() + '%'

    total = oracle_db.scalar(f"SELECT COUNT(*) FROM {MUTASI_FROM} {where}", binds)
    pages = max(math.ceil(total / PER_PAGE), 1)
    page = min(page, pages)

    sql = (
        f"SELECT * FROM ("
        f" SELECT a.*, ROWNUM rn FROM ("
        f"  SELECT t.NIK_STAFF, e.EMPNAME, t.TERMINATE_DATE, t.TERM_TYPE, "
        f"  t.TERM_TYPE_ID, t.MUTATION_SITE, t.SISA_CUTI, t.REASON_OF_RESIGN "
        f"  FROM {MUTASI_FROM} {where} "
        f"  ORDER BY t.TERMINATE_DATE DESC, t.NIK_STAFF) a"
        f" WHERE ROWNUM <= :hi) WHERE rn > :lo"
    )
    rows = oracle_db.fetch_all(
        sql, dict(binds, hi=page * PER_PAGE, lo=(page - 1) * PER_PAGE))

    nama_site = {s[0]: s[1] for s in _daftar_site(comp)}
    jenis = dict(JENIS_TRANSAKSI)
    for r in rows:
        r['TGL'] = r['TERMINATE_DATE'].strftime('%d-%m-%Y') if r['TERMINATE_DATE'] else ''
        r['JENIS'] = jenis.get(r['TERM_TYPE'], r['TERM_TYPE'] or '')
        ms = r['MUTATION_SITE']
        r['SITE_TUJUAN'] = nama_site.get(ms, ms) if ms else ''
        cuti = r['SISA_CUTI']
        r['CUTI'] = '' if cuti is None else (int(cuti) if float(cuti).is_integer() else cuti)

    konteks.update({'rows': rows, 'q': q, 'page': page, 'pages': pages,
                    'total': total, 'prev': page - 1, 'next': page + 1})
    return render(request, 'biodata/mutasi_list.html', konteks)


@comp_site_required
@permission_required('biodata.tambah_mutasi', raise_exception=True)
def mutasi_tambah(request):
    comp, site = _scope(request)
    if not TABLE_MUTASI:
        messages.error(request, 'ORA_TABLE_MUTASI belum diisi di .env.')
        return redirect('biodata:mutasi')

    sites = [s for s in _daftar_site(comp) if s[0] != site]
    kode_jenis = [k for k, _ in JENIS_TRANSAKSI]
    alasan = [r['TERM_TYPE_ID'] for r in oracle_db.fetch_all(
        f"SELECT DISTINCT TERM_TYPE_ID FROM {TABLE_MUTASI} "
        f"WHERE COMP_ID = :c AND SITE_ID = :s AND TERM_TYPE_ID IS NOT NULL "
        f"ORDER BY 1", {'c': comp, 's': site})]

    raw, errors = {}, {}
    if request.method == 'POST':
        kolom = ['NIK_STAFF', 'TERM_TYPE', 'MUTATION_SITE', 'TERMINATE_DATE',
                 'TERM_TYPE_ID', 'SISA_CUTI', 'REASON_OF_RESIGN']
        raw = {k: request.POST.get(k, '').strip() for k in kolom}
        mutasi = raw['TERM_TYPE'] == KODE_MUTASI

        # NIK: wajib, muat di kolom 15 karakter, dan harus pekerja Comp/Site ini
        if not raw['NIK_STAFF']:
            errors['NIK_STAFF'] = 'Wajib diisi'
        elif len(raw['NIK_STAFF'].encode('utf-8')) > 15:
            errors['NIK_STAFF'] = 'Lebih dari 15 karakter, tidak muat di tabel ini'
        elif not oracle_db.scalar(
                f"SELECT COUNT(*) FROM {TABLE} WHERE {KEY_WHERE}",
                {'c': comp, 's': site, 'e': raw['NIK_STAFF']}):
            errors['NIK_STAFF'] = 'Pekerja tidak ditemukan di Perusahaan/Site ini'

        if raw['TERM_TYPE'] not in kode_jenis:
            errors['TERM_TYPE'] = 'Pilih jenis transaksi'

        tujuan = None
        if mutasi:
            if raw['MUTATION_SITE'] not in [s[0] for s in sites]:
                errors['MUTATION_SITE'] = 'Pilih site tujuan dari daftar'
            else:
                tujuan = raw['MUTATION_SITE']

        tgl = None
        if not raw['TERMINATE_DATE']:
            errors['TERMINATE_DATE'] = 'Wajib diisi'
        else:
            try:
                tgl = datetime.strptime(raw['TERMINATE_DATE'], '%Y-%m-%d')
            except ValueError:
                errors['TERMINATE_DATE'] = 'Tanggal tidak valid'

        if not raw['TERM_TYPE_ID']:
            if raw['TERM_TYPE'] and not mutasi:
                errors['TERM_TYPE_ID'] = 'Wajib diisi untuk Keluar'
        elif len(raw['TERM_TYPE_ID'].encode('utf-8')) > 15:
            errors['TERM_TYPE_ID'] = 'Maksimal 15 karakter'

        cuti = None
        if raw['SISA_CUTI']:
            try:
                cuti = Decimal(raw['SISA_CUTI'].replace(',', '.'))
                if cuti < 0:
                    errors['SISA_CUTI'] = 'Tidak boleh negatif'
            except InvalidOperation:
                errors['SISA_CUTI'] = 'Angka tidak valid'

        if not raw['REASON_OF_RESIGN']:
            errors['REASON_OF_RESIGN'] = 'Wajib diisi'
        elif len(raw['REASON_OF_RESIGN'].encode('utf-8')) > 1000:
            errors['REASON_OF_RESIGN'] = 'Maksimal 1000 karakter'

        if not errors:
            sudah = oracle_db.scalar(
                f"SELECT COUNT(*) FROM {TABLE_MUTASI} "
                f"WHERE COMP_ID = :c AND SITE_ID = :s AND NIK_STAFF = :e "
                f"AND TRUNC(TERMINATE_DATE) = :tgl",
                {'c': comp, 's': site, 'e': raw['NIK_STAFF'], 'tgl': tgl})
            if sudah:
                errors['TERMINATE_DATE'] = 'Pekerja ini sudah punya transaksi di tanggal tersebut'

        if errors:
            messages.error(request, 'Periksa kembali isian yang bertanda merah.')
        else:
            sql = (f"INSERT INTO {TABLE_MUTASI} "
                   f"(COMP_ID, SITE_ID, NIK_STAFF, TERMINATE_DATE, TERM_TYPE, "
                   f"TERM_TYPE_ID, MUTATION_SITE, SISA_CUTI, REASON_OF_RESIGN, "
                   f"INPUTBY, INPUTDATE) "
                   f"VALUES (:c, :s, :e, :tgl, :jenis, :alasan, :tujuan, :cuti, "
                   f":reason, :inputby, SYSDATE)")
            binds = {'c': comp, 's': site, 'e': raw['NIK_STAFF'], 'tgl': tgl,
                     'jenis': raw['TERM_TYPE'],
                     'alasan': raw['TERM_TYPE_ID'] or None,
                     'tujuan': tujuan, 'cuti': cuti,
                     'reason': raw['REASON_OF_RESIGN'],
                     'inputby': request.user.username[:30]}
            try:
                oracle_db.execute(sql, binds)
            except cx_Oracle.IntegrityError:
                errors['TERMINATE_DATE'] = 'Data dengan kunci ini sudah ada'
            except cx_Oracle.DatabaseError as exc:
                messages.error(request, f'Gagal menyimpan ke Oracle: {exc}')
            else:
                messages.success(request, 'Transaksi berhasil ditambahkan.')
                return redirect('biodata:mutasi')

    return render(request, 'biodata/mutasi_form.html', {
        'raw': raw, 'errors': errors, 'jenis': JENIS_TRANSAKSI,
        'kode_mutasi': KODE_MUTASI, 'sites': sites, 'alasan': alasan,
    })