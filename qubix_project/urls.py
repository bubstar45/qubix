from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views  # Add this import

urlpatterns = [
    # ============= IMPERSONATION URLs - MUST COME BEFORE admin/ =============
    path('admin/impersonate/start/<int:user_id>/', views.admin_impersonate_start, name='admin_impersonate_start'),
    path('admin/impersonate/stop/', views.admin_impersonate_stop, name='admin_impersonate_stop'),
    
    # ============= ADMIN URL =============
    path('admin/', admin.site.urls),
    
    # ============= CORE APP URLs =============
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)