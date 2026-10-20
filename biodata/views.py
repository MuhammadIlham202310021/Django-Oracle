import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

import cx_Oracle
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from . import oracle_db
from .fields import AUDIT, FIELDS, LIST_COLUMNS, SECTIONS, SENSITIVE

TABLE = oracle_db.TABLE
PER_PAGE = 25
KEY_WHERE = "COMP_ID = :c AND SITE_ID = :s AND EMPCODE = :e"


@login_required
def home(request):
    return render(request, 'biodata/home.html')

# Lihat Data
@login_required
def biodata_list(request):
    q = request.GET.get('q', '').strip()
    try:
        page = max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        page = 1

    where, binds = '', {}
    if q:
        where = "WHERE UPPER(EMPCODE) LIKE :q OR UPPER(EMPNAME) LIKE :q"
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
        'columns': LIST_COLUMNS,
    })

# Lihat Data secara keseluruhan
@login_required
def biodata_detail(request):
    binds = {'c': request.GET.get('comp', ''),
             's': request.GET.get('site', ''),
             'e': request.GET.get('code', '')}
    cols = ", ".join([f[0] for f in FIELDS] + AUDIT)
    row = oracle_db.fetch_one(
        f"SELECT {cols} FROM {TABLE} WHERE {KEY_WHERE}", binds)
    if not row:
        raise Http404("Data tidak ditemukan")

    def show(col, value):
        if col in SENSITIVE and not request.user.is_superuser:
            return '(dibatasi)'
        if isinstance(value, datetime):
            return value.strftime('%d-%m-%Y')
        return '' if value is None else value

    sections = [
        (title, [(label, show(col, row[col])) for col, label, *_ in fields])
        for title, fields in SECTIONS
    ]
    audit = [(c, show(c, row[c])) for c in AUDIT]
    return render(request, 'biodata/detail.html', {
        'sections': sections, 'audit': audit,
        'name': row['EMPNAME'], 'code': row['EMPCODE'],
    })

# kolom kosong menghasilkan error hanya jika wajib
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

# menyiapkan data untuk template
def _form_sections(raw_values, errors):
    return [
        {'title': title, 'fields': [
            {'name': f[0], 'label': f[1], 'type': f[2], 'length': f[3],
             'req': f[4], 'value': raw_values.get(f[0], ''),
             'error': errors.get(f[0])}
            for f in fields]}
        for title, fields in SECTIONS
    ]

# Tambah Data biodata
@login_required
def biodata_create(request):
    raw_values, errors = {}, {}

    if request.method == 'POST':
        raw_values = {f[0]: request.POST.get(f[0], '') for f in FIELDS}
        parsed = {}
        for f in FIELDS:
            value, err = _parse(f, raw_values[f[0]])
            if err:
                errors[f[0]] = err
            else:
                parsed[f[0]] = value

        if not errors:
            key = {'c': parsed['COMP_ID'], 's': parsed['SITE_ID'],
                   'e': parsed['EMPCODE']}
            exists = oracle_db.scalar(
                f"SELECT COUNT(*) FROM {TABLE} WHERE {KEY_WHERE}", key)
            if exists:
                errors['EMPCODE'] = ('Kombinasi Perusahaan, Site, dan Kode '
                                     'Pekerja ini sudah ada')

        if not errors:
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
                    '/biodata/lihat/?comp=%s&site=%s&code=%s'
                    % (key['c'], key['s'], key['e']))

        if errors:
            messages.error(request, 'Periksa kembali isian yang bertanda merah.')

    return render(request, 'biodata/form.html',
                  {'sections': _form_sections(raw_values, errors)})
