from django.urls import path
from .views import UserRegistration, UserLogin, UserChangePassword

urlpatterns = [
    path('register/', UserRegistration.as_view(), name='user-register'),
    path('login/', UserLogin.as_view(), name='user-login'),
    path('change-password/', UserChangePassword.as_view(), name='user-change-password'),
]
