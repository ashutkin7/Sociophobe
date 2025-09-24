from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Users
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserChangePasswordSerializer
)

tag = ['Пользователь']


class UserRegistration(APIView):
    @extend_schema(
        summary="Регистрация пользователя",
        description="Создание нового пользователя с ролью respondent/customer/moderator. Проверка simple-captcha.",
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=inline_serializer(
                    name='UserRegistrationSuccess',
                    fields={'user_id': serializers.IntegerField(help_text='ID зарегистрированного пользователя')}
                ),
                description="Пользователь успешно зарегистрирован"
            ),
            400: OpenApiResponse(description="Ошибки валидации")
        },
        tags=tag
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"user_id": user.user_id}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLogin(APIView):
    @extend_schema(
        summary="Вход пользователя",
        description="Аутентификация по email и паролю с проверкой simple-captcha.",
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='UserLoginSuccess',
                    fields={'user_id': serializers.IntegerField(help_text='ID аутентифицированного пользователя')}
                ),
                description="Вход выполнен успешно"
            ),
            401: OpenApiResponse(description="Неверный email или пароль")
        },
        tags=tag
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']

            # стандартная Django аутентификация
            user = authenticate(request, username=email, password=password)
            if user:
                return Response({"user_id": user.user_id}, status=status.HTTP_200_OK)
            return Response({"error": "Неверный email или пароль"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserChangePassword(APIView):
    @extend_schema(
        summary="Смена пароля",
        description="Смена пароля после проверки текущего пароля и simple-captcha.",
        request=UserChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='ChangePasswordSuccess',
                    fields={'message': serializers.CharField(help_text='Сообщение об успешной смене пароля')}
                ),
                description="Пароль успешно изменен"
            ),
            400: OpenApiResponse(description="Ошибки валидации"),
            401: OpenApiResponse(description="Неверный текущий пароль или пользователь не найден")
        },
        tags=tag
    )
    def post(self, request):
        serializer = UserChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            old_password = serializer.validated_data['old_password']
            new_password = serializer.validated_data['new_password']
            try:
                user = Users.objects.get(email=email)
            except Users.DoesNotExist:
                return Response({"error": "Пользователь не найден"}, status=status.HTTP_401_UNAUTHORIZED)
            if not user.check_password(old_password):
                return Response({"error": "Неверный текущий пароль"}, status=status.HTTP_401_UNAUTHORIZED)
            user.set_password(new_password)
            user.save()
            return Response({"message": "Пароль успешно изменен"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
