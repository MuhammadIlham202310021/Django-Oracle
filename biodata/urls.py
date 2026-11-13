from django.urls import path

from . import views

app_name = 'biodata'

urlpatterns = [
    path('', views.home, name='home'),
    path('biodata/', views.biodata_list, name='list'),
    path('biodata/ubah/', views.biodata_edit, name='edit'),
    path('biodata/tambah/', views.biodata_create, name='create'),
    path('biodata/taxstatus/', views.taxstatus, name='taxstatus'),
    path('biodata/karier/', views.karier, name='karier'),
    path('mutasi/', views.mutasi_list, name='mutasi'),
    path('mutasi/tambah/', views.mutasi_tambah, name='mutasi_tambah'),
]