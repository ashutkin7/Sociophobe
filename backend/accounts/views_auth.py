from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Users
from .serializers_auth import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer
)

tag_auth = ['Авторизация']


class UserRegistration(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Регистрация пользователя",
        description="Создание нового пользователя с ролью respondent/customer/moderator. Проверка simple-captcha.",
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=inline_serializer(
                    name='UserRegistrationSuccess',
                    fields={'user_id': serializers.IntegerField()}
                ),
                description="Пользователь успешно зарегистрирован"
            )
        },
        tags=tag_auth
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"user_id": user.user_id}, status=status.HTTP_201_CREATED)


class UserLogin(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Вход пользователя (JWT)",
        description="Аутентификация по email/паролю с simple-captcha и выдачей JWT токенов.",
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='UserLoginSuccess',
                    fields={
                        'refresh': serializers.CharField(),
                        'access': serializers.CharField()
                    }
                ),
                description="JWT токены"
            ),
            401: OpenApiResponse(description="Неверный email или пароль")
        },
        tags=tag_auth
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(request, username=email, password=password)
        if not user:
            return Response({"error": "Неверный email или пароль"},
                            status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        })


class UserChangePassword(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Смена пароля (JWT)",
        request=UserChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='ChangePasswordSuccess',
                    fields={'message': serializers.CharField()}
                ),
                description="Пароль успешно изменен"
            ),
            401: OpenApiResponse(description="Неверный текущий пароль")
        },
        tags=tag_auth
    )
    def post(self, request):
        serializer = UserChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        if not request.user.check_password(old_password):
            return Response({"error": "Неверный текущий пароль"},
                            status=status.HTTP_401_UNAUTHORIZED)
        request.user.set_password(new_password)
        request.user.save()
        return Response({"message": "Пароль успешно изменен"})

class ForgotPassword(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Инициация восстановления пароля",
        description="Отправляет письмо с токеном для смены пароля.",
        request=ForgotPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='ForgotPasswordSuccess',
                    fields={'message': serializers.CharField()}
                ),
                description="Письмо отправлено, если email зарегистрирован"
            )
        },
        tags=tag_auth
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = Users.objects.get(email=email)
        except Users.DoesNotExist:
            # Не раскрываем, существует ли email
            return Response({"message": "Если email зарегистрирован, письмо отправлено"},
                            status=status.HTTP_200_OK)

        token = default_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}&email={email}"

        send_mail(
            subject="Восстановление пароля",
            message=f"Для смены пароля перейдите по ссылке: {reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
        return Response({"message": "Если email зарегистрирован, письмо отправлено"},
                        status=status.HTTP_200_OK)


class ResetPassword(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Смена пароля по токену",
        description="Завершение процедуры восстановления пароля с помощью токена из письма.",
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='ResetPasswordSuccess',
                    fields={'message': serializers.CharField()}
                ),
                description="Пароль успешно изменен"
            ),
            400: OpenApiResponse(description="Неверный токен или email")
        },
        tags=tag_auth
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        email = request.query_params.get('email') or request.data.get('email')
        if not email:
            return Response({"error": "Не указан email"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user = Users.objects.get(email=email)
        except Users.DoesNotExist:
            return Response({"error": "Неверный email"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, token):
            return Response({"error": "Неверный или просроченный токен"},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Пароль успешно изменен"},
                        status=status.HTTP_200_OK)