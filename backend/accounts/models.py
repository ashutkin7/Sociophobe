from django.db import models
from django.contrib.auth.hashers import make_password, check_password

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.models import BaseUserManager

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
    role = models.CharField(max_length=100, choices=[
        ('respondent', 'Respondent'),
        ('customer', 'Customer'),
        ('moderator', 'Moderator')
    ])

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'role']

    objects = UsersManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.email} ({self.role})"
