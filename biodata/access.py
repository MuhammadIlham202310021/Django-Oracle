from functools import wraps

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

# === Login dan akses ===
def comp_site_required(view):
    """Wajib login DAN punya Comp/Site di session."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('comp_id') or not request.session.get('site_id'):
            logout(request)
            return redirect('login')
        return view(request, *args, **kwargs)
    return wrapper

def _scope(request):
    return request.session['comp_id'], request.session['site_id']    

def _boleh_sensitif(user):
    return user.has_perm('biodata.lihat_sensitif')
# === End Login dan akses ===

  
  
