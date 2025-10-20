from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.dispatch import receiver
from django.db.models.signals import post_migrate

class UsersManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser должен иметь is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser должен иметь is_superuser=True')
        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        """Позволяет аутентифицировать по email"""
        return self.get(email=email)


class Users(AbstractBaseUser, PermissionsMixin):
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=100,
        choices=[
            ('respondent', 'Respondent'),
            ('customer', 'Customer'),
            ('moderator', 'Moderator')
        ]
    )

    # флаг завершённости профиля
    is_profile_complete = models.BooleanField(
        default=False,
        help_text="Отмечает, завершил ли пользователь заполнение личного профиля"
    )

    # стандартные флаги для кастомной модели пользователя
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'role']

    objects = UsersManager()

    @property
    def id(self):
        return self.user_id

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.email} ({self.role})"


class Characteristics(models.Model):
    TYPE_CHOICES = [
        ('numeric', 'Числовой'),
        ('string', 'Строковый'),
        ('choice', 'Выбор'),
    ]

    characteristic_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    value_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    requirements = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'characteristics'


class CharacteristicValues(models.Model):
    characteristic_value_id = models.AutoField(primary_key=True)
    characteristic = models.ForeignKey(Characteristics, on_delete=models.CASCADE)
    value_text = models.CharField(max_length=255)

    class Meta:
        db_table = 'characteristic_values'


class RespondentCharacteristics(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    characteristic_value = models.ForeignKey(CharacteristicValues, on_delete=models.CASCADE)

    # ✅ Новое поле (оценка качества соответствия)
    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Оценка соответствия характеристике (от 0 до 1)"
    )

    class Meta:
        db_table = 'respondent_characteristics'
        unique_together = (('user', 'characteristic_value'),)

    def clean(self):
        # Автоматическая валидация диапазона 0–1
        if self.score is not None and not (0.0 <= self.score <= 1.0):
            from django.core.exceptions import ValidationError
            raise ValidationError("Поле 'score' должно быть в диапазоне от 0 до 1")

    def __str__(self):
        return f"{self.user.email} → {self.characteristic_value} ({self.score})"

# ============================================================
# 🔹 Автозаполнение таблицы характеристик после миграции
# ============================================================
@receiver(post_migrate)
def create_default_characteristics(sender, **kwargs):
    """
    Автоматически создаёт стандартные характеристики, если их нет в БД.
    Формат requirements:
      - для choice: варианты через запятую
      - для numeric: минимум,максимум
    """
    if sender.name not in ['accounts', 'analytics']:
        return

    defaults = [
        {
            "name": "Возраст",
            "value_type": "numeric",
            "requirements": "10,100",  # минимальный и максимальный возраст
        },
        {
            "name": "Пол",
            "value_type": "choice",
            "requirements": "Мужской,Женский,Другое",  # варианты выбора
        },
        {
            "name": "Город",
            "value_type": "string",
            "requirements": "",  # свободный ввод
        },
        {
            "name": "Образование",
            "value_type": "choice",
            "requirements": "Среднее,Среднее специальное,Высшее,Магистр,Кандидат наук,Доктор наук",
        },
        {
            "name": "Профессия",
            "value_type": "string",
            "requirements": "",
        },
        {
            "name": "Доход",
            "value_type": "numeric",
            "requirements": "0,1000000",  # диапазон дохода в рублях
        },
        {
            "name": "Семейное положение",
            "value_type": "choice",
            "requirements": "Холост,Женат,Разведён,В отношениях",
        },
        {
            "name": "Опыт работы",
            "value_type": "numeric",
            "requirements": "0,50",  # количество лет опыта
        },
        {
            "name": "Уровень удовлетворенности жизнью",
            "value_type": "numeric",
            "requirements": "1,10",  # шкала от 1 до 10
        },
        {
            "name": "Наличие детей",
            "value_type": "choice",
            "requirements": "Да,Нет",
        },
    ]

    for item in defaults:
        obj, created = Characteristics.objects.get_or_create(
            name=item["name"],
            defaults={
                "value_type": item["value_type"],
                "requirements": item["requirements"],
            },
        )
        if created:
            print(f"[INIT] ✅ Добавлена характеристика: {obj.name}")