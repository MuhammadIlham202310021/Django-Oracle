from urllib.parse import quote

import cx_Oracle
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .. import oracle_db
from ..access import _scope, comp_site_required
from ..constants import KEY_WHERE, TABLE, TABLE_TAX, TAX_KEY_WHERE
from ..fields import KODE_BERAS, KODE_PAJAK
from ..helpers import _tampil

# === Tab Tax Status ===
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
# === End Tab Tax Status ===