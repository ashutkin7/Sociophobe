from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('captcha/', include('captcha.urls')),
    path('api/', include('accounts.urls')),
    path('api/surveys/', include('surveys.urls')),
    path('api/AI/', include('AI.urls')),
]
