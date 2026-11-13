from datetime import datetime
from urllib.parse import quote

import cx_Oracle
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .. import oracle_db
from ..access import _scope, comp_site_required
from ..constants import (KARIER_BOLEH_MASA_DEPAN, KARIER_TEKS, KEY_WHERE,
                         NIK_WHERE, TABLE, TABLE_JOBSPEC, TABLE_KARIER)
from ..helpers import _tampil

# === Tab Riwayat Karir ===
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
                errors[col] = 'Wajib diisi'
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
                   f":inputby, SYSDATE)")
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
 # === End Tab Riwayat Karir ===