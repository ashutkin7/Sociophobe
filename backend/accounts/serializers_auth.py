from rest_framework import serializers
from .models import Users
from captcha.models import CaptchaStore

class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[
        ('respondent', 'Respondent'),
        ('customer', 'Customer'),
    ])
    password = serializers.CharField(write_only=True)
    captcha_key = serializers.CharField(write_only=True)
    captcha_value = serializers.CharField(write_only=True)

    def validate(self, data):
        key = data.get('captcha_key')
        value = data.get('captcha_value')

        # Проверка наличия капчи
        if not key or not value:
            raise serializers.ValidationError("Требуется ввести капчу.")

        # Проверка существования ключа
        try:
            captcha = CaptchaStore.objects.get(hashkey=key)
        except CaptchaStore.DoesNotExist:
            raise serializers.ValidationError("Ключ капчи не найден или устарел. Обновите капчу.")

        # Проверка совпадения
        if captcha.response != value.strip().lower():
            raise serializers.ValidationError("Неверно введена капча. Попробуйте снова.")

        # Капча проверена успешно — удаляем её
        captcha.delete()
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('captcha_key', None)
        validated_data.pop('captcha_value', None)

        user = Users(**validated_data)
        user.set_password(password)
        user.save()
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)



class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


# ➕ Для восстановления пароля
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Email пользователя для восстановления")


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Токен из письма для подтверждения")
    new_password = serializers.CharField(write_only=True, help_text="Новый пароль")
