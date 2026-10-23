from django.db import models
from django.conf import settings

# Create your models here.
class AksesUser(models.Model):
    # Daftar Comp/site yang boleh dipakai oleh seorang user
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name='akses')
    comp_id = models.CharField(max_length=6)
    site_id = models.CharField(max_length=6)
    
    class Meta:
        unique_together = ('user', 'comp_id', 'site_id')
        verbose_name = 'Akses User'
        verbose_name_plural = 'Akses User'
        
    def __str__(self):
        return f'{self.user} - {self.comp_id}/{self.site_id}'