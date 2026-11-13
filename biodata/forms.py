import logging

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from . import oracle_db
from .models import AksesUser

logger = logging.getLogger(__name__)


def _ambil_pasangan():
    """Baca daftar perusahaan dan site dari view referensi.

    Hasil: {comp_id: {'name': nama_comp, 'sites': [[site_id, nama_site], ...]}}
    """
    sql = (f"SELECT DISTINCT COMP_ID, COMP_NAME, SITE_ID, SITE_NAME "
           f"FROM {oracle_db.VIEW_COMPSITE} ORDER BY COMP_ID, SITE_ID")
    comps = {}
    for r in oracle_db.fetch_all(sql):
        comp_id, site_id = r['COMP_ID'], r['SITE_ID']
        if comp_id is None or site_id is None:
            continue                      # tanpa pasangan lengkap, tidak bisa dipilih
        comp_id, site_id = str(comp_id), str(site_id)
        info = comps.setdefault(
            comp_id, {'name': r['COMP_NAME'] or comp_id, 'sites': []})
        info['sites'].append([site_id, r['SITE_NAME'] or site_id])
    return comps


class CompSiteLoginForm(AuthenticationForm):
    comp_id = forms.ChoiceField(
        label='Perusahaan', widget=forms.Select(attrs={'class': 'form-select'}))
    site_id = forms.ChoiceField(
        label='Site', widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_error = ''
        try:
            self.pairs = _ambil_pasangan()
        except Exception as exc:
            logger.exception('Gagal membaca daftar Comp/Site dari Oracle')
            self.pairs = {}
            self.load_error = f'{type(exc).__name__}: {exc}'

        self.fields['comp_id'].choices = (
            [('', 'Pilih Perusahaan')]
            + [(cid, info['name']) for cid, info in self.pairs.items()])

        # urutan penting: semua_site harus dibuat SEBELUM dipakai di bawah
        semua_site = {sid: nama
                      for info in self.pairs.values()
                      for sid, nama in info['sites']}
        self.fields['site_id'].choices = (
            [('', 'Pilih Site')]
            + sorted(semua_site.items(), key=lambda kv: str(kv[1])))

    def nama(self, comp, site):
        """Kembalikan (nama_comp, nama_site) untuk disimpan di session."""
        info = self.pairs[comp]
        return info['name'], dict(info['sites'])[site]

    def clean(self):
        cleaned = super().clean()
        user = self.get_user()
        comp = cleaned.get('comp_id')
        site = cleaned.get('site_id')

        if user and comp and site:
            site_valid = [s[0] for s in self.pairs.get(comp, {}).get('sites', [])]
            if site not in site_valid:
                raise forms.ValidationError(
                    'Site tidak sesuai dengan Perusahaan yang dipilih.')
            if not user.is_superuser and not AksesUser.objects.filter(
                    user=user, comp_id=comp, site_id=site).exists():
                raise forms.ValidationError(
                    'Anda tidak memiliki akses ke Perusahaan dan Site tersebut.')
        return cleaned