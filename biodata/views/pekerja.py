import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import cx_Oracle
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .. import oracle_db
from ..access import _boleh_sensitif, _scope, comp_site_required
from ..constants import (DIKUNCI_PAJAK, KEY_WHERE, LOCKED, PER_PAGE,
                         SCOPE_WHERE, TAB_KUNCI, TABLE)
from ..fields import AUDIT, FIELDS, LIST_COLUMNS, SECTIONS, SENSITIVE
from ..helpers import _ke_input, _tampil


# === Fungsi bantu form biodata ===
def _kolom_aktif(user, mode):
    """Kolom yang tampil di form DAN boleh disimpan oleh user ini."""
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
# === End Fungsi bantu form biodata ===

# === Biodata daftar ===
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
# === End Biodata: daftar ===
 
# === Biodata: lihat dan ubah ===
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
# === End Biodata: lihat dan ubah ===

# === Biodata: tambah ===
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
# === End Biodata: tambah ===