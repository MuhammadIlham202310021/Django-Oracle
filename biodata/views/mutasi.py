import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

import cx_Oracle
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render

from .. import oracle_db
from ..access import _scope, comp_site_required
from ..constants import KEY_WHERE, MUTASI_FROM, PER_PAGE, TABLE, TABLE_MUTASI
from ..fields import JENIS_TRANSAKSI, KODE_MUTASI
from ..forms import _ambil_pasangan

# === Mutasi dan Termination: fungsi bantu ===
def _daftar_site(comp):
    """[[site_id, nama_site], ...] untuk perusahaan ini, dari VW_REF_COMPSITE."""
    try:
        return _ambil_pasangan().get(comp, {}).get('sites', [])
    except Exception:
        return []
# === End fungsi bantu ===

# === Mutasi dan Termination: daftar ===
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
# === End Mutasi dan Termination: daftar ===

# === Mutasi dan Termination: tambah ===
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
# === End Mutasi dan Termination: tambah ===
   