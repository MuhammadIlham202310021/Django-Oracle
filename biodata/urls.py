from django.urls import path

from . import views

app_name = 'biodata'

urlpatterns = [
    path('', views.home, name='home'),
    path('biodata/', views.biodata_list, name='list'),
    path('biodata/lihat/', views.biodata_detail, name='detail'),
    path('biodata/tambah/', views.biodata_create, name='create'),
]