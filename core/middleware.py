# core/middleware.py
import pytz
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib.auth import logout

class TimezoneMiddleware:
    """Activate user's timezone if they have one set"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ✅ FIX: Check if user attribute exists first
        if hasattr(request, 'user') and request.user.is_authenticated and hasattr(request.user, 'timezone') and request.user.timezone:
            try:
                timezone.activate(pytz.timezone(request.user.timezone))
            except:
                timezone.activate('UTC')
        else:
            timezone.deactivate()
        
        return self.get_response(request)


class SessionTimeoutMiddleware:
    """Log out inactive users after 30 minutes"""
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout_minutes = 30

    def __call__(self, request):
        # ✅ FIX: Check if user attribute exists first
        if hasattr(request, 'user') and request.user.is_authenticated and not request.path.startswith('/admin/'):
            last_activity = request.session.get('last_activity')
            current_time = timezone.now()
            
            if last_activity:
                if isinstance(last_activity, str):
                    from dateutil import parser
                    last_activity = parser.parse(last_activity)
                
                elapsed_time = (current_time - last_activity).total_seconds() / 60
                
                if elapsed_time > self.timeout_minutes:
                    logout(request)
                    request.session.flush()
                    return redirect('login')
            
            request.session['last_activity'] = current_time.isoformat()
        
        return self.get_response(request)