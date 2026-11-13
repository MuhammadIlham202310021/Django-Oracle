# Meneruskan semua view agar urls.py, config/urls.py, dan settings.py tidak berubah.
# Ini yang membuat from . import views dan views.home di urls.py serta CSRF_FAILURE_VIEW = 'biodata.views.csrf_gagal' tetap berjalan. Setelah
from .umum import CompSiteLoginView, csrf_gagal, home
from .pekerja import biodata_create, biodata_edit, biodata_list
from .tab_tax import taxstatus
from .tab_karier import karier
from .mutasi import mutasi_list, mutasi_tambah