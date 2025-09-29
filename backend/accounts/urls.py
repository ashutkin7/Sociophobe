from django.urls import path
from .views_auth import (
    UserRegistration, UserLogin, UserChangePassword,
    ForgotPassword, ResetPassword
)
from .views_profile import UserMeView, UserStatsView

urlpatterns = [
    # Авторизация
    path('auth/register/', UserRegistration.as_view(), name='register'),
    path('auth/login/', UserLogin.as_view(), name='login'),
    path('auth/change-password/', UserChangePassword.as_view(), name='change-password'),
    path('auth/forgot-password/', ForgotPassword.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPassword.as_view(), name='reset-password'),

    # Личный кабинет
    path('users/me/', UserMeView.as_view(), name='user-me'),
    path('users/me/stats/', UserStatsView.as_view(), name='user-stats'),
]
