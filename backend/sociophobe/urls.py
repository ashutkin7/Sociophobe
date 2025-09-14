from django.urls import path, include
from accounts.views import RegisterView, LoginView
from django.contrib import admin
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/password_reset/', include('django_rest_passwordreset.urls', namespace='password_reset')),
    path('captcha/', include('captcha.urls')),
]
