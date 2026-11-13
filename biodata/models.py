from django.conf import settings
from django.db import models

class AksesUser(models.Model):
    """Daftar Comp/Site yang boleh dipakai oleh seorang user."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name='akses')
    comp_id = models.CharField(max_length=6)
    site_id = models.CharField(max_length=6)

    class Meta:
        unique_together = ('user', 'comp_id', 'site_id')
        verbose_name = 'Akses User'
        verbose_name_plural = 'Akses User'
        permissions = [
            ('tambah_biodata', 'Boleh menambah biodata'),
            ('ubah_biodata', 'Boleh mengubah biodata'),
            ('lihat_sensitif', 'Boleh melihat dan mengisi kolom sensitif'),
            ('tambah_taxstatus', 'Boleh menambah tax status'),
            ('tambah_karier', 'Boleh menambah riwayat karir'),
            ('lihat_mutasi', 'Boleh melihat mutasi dan termination'),
            ('tambah_mutasi', 'Boleh menambah mutasi dan termination'),
        ]

    def __str__(self):
        return f'{self.user} - {self.comp_id}/{self.site_id}'