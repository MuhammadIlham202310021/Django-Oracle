from django.contrib import admin

# Register your models here.
from .models import AksesUser

# mendaftarkan tabel tadi ke halaman /admin/, tempat Anda mengatur akses user.
@admin.register(AksesUser)
class AksesUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'comp_id', 'site_id')
    list_filter = ('comp_id', 'site_id')
    search_fields = ('user__username',)
    
