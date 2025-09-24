from rest_framework import serializers
from captcha.fields import CaptchaField
from .models import Users   # подключаем вашу модель

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
        # captcha уже провалидирована и не нужна для создания пользователя
        validated_data.pop('captcha', None)   # ✅ безопасно
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
    email = serializers.EmailField()
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    captcha = CaptchaField()
