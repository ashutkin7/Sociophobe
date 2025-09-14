from django.db import models
from django.contrib.auth.hashers import make_password, check_password

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

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
    REQUIRED_FIELDS = ['password']

    class Meta:
        managed = True
        db_table = 'users'

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.email} ({self.role})"

