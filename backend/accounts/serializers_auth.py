from rest_framework import serializers
from captcha.fields import CaptchaField
from .models import Users

class UserRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[
        ('respondent', 'Respondent'),
        ('customer', 'Customer'),
        ('moderator', 'Moderator')
    ])
    password = serializers.CharField(write_only=True)
    captcha = CaptchaField()

    def create(self, validated_data):
        validated_data.pop('captcha', None)
        password = validated_data.pop('password')
        user = Users(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    captcha = CaptchaField()


class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


# ➕ Для восстановления пароля
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Email пользователя для восстановления")


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Токен из письма для подтверждения")
    new_password = serializers.CharField(write_only=True, help_text="Новый пароль")
