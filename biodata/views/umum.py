from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from ..access import comp_site_required
from ..forms import CompSiteLoginForm

# === Login dan CSRF ===
class CompSiteLoginView(LoginView):
    authentication_form = CompSiteLoginForm
    
    def form_valid(self, form):
        response = super().form_valid(form)
        comp = form.cleaned_data['comp_id']
        site = form.cleaned_data['site_id']
        nama_comp, nama_site = form.nama(comp, site)
        # ID dipakai untuk filter query, nama hanya untuk tampilan
        self.request.session['comp_id'] = comp
        self.request.session['site_id'] = site
        self.request.session['comp_name'] = nama_comp
        self.request.session['site_name'] = nama_site
        return response 
    
def csrf_gagal(request, reason=''):
    """Dipanggil Django saat token CSRF usang atau hilang.

    redirect(request.path) membuka kembali halaman yang sama lewat GET,
    sehingga form dimuat dengan token baru. Isian yang tadi diketik hilang,
    tetapi pesannya menjelaskan alasannya.
    """
    messages.error(
        request,
        'Halaman sudah kedaluwarsa Silahkan login ulang kembali.')
    return redirect(request.path)
# === End Login dan CSRF ===

# === Halaman HOME ===
@comp_site_required
def home(request):
    return render(request, 'biodata/home.html')
# === End Halaman HOME ===

