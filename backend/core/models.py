from django.db import models
from django.contrib.auth.hashers import make_password, check_password

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

from accounts.models import Users
from surveys.models import Surveys, Questions, SurveyQuestions, RespondentAnswers

class Characteristics(models.Model):
    characteristic_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'characteristics'


class CharacteristicValues(models.Model):
    characteristic_value_id = models.AutoField(primary_key=True)
    characteristic = models.ForeignKey(Characteristics, on_delete=models.CASCADE)
    value_text = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'characteristic_values'


class RespondentCharacteristics(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    characteristic_value = models.ForeignKey(CharacteristicValues, on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = 'respondent_characteristics'
        unique_together = (('user', 'characteristic_value'),)



class Dashboards(models.Model):
    dashboard_id = models.AutoField(primary_key=True)
    survey = models.OneToOneField(Surveys, on_delete=models.CASCADE)
    row_n = models.IntegerField()
    column_n = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'dashboards'


class Analytics(models.Model):
    analytics_id = models.AutoField(primary_key=True)
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE)
    question = models.ForeignKey(Questions, on_delete=models.CASCADE)
    diagram_id = models.IntegerField(null=True, blank=True)
    type_diagram = models.CharField(max_length=255, null=True, blank=True)
    data_diagram = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'analytics'
