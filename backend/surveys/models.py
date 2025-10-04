from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

class Surveys(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('stopped', 'Stopped'),
        ('finished', 'Finished'),
    ]

    TYPE_CHOICES = [
        ('simple', 'Простой'),
        ('extended', 'Расширенный'),
    ]

    survey_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_finished = models.DateTimeField(null=True, blank=True)
    max_residents = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    type_survey = models.CharField(max_length=20, choices=TYPE_CHOICES, default='simple')

    class Meta:
        db_table = 'surveys'
        managed = True

    def is_active(self):
        if self.status != 'active':
            return False
        if self.date_finished and timezone.now() > self.date_finished:
            return False
        return True


class Questions(models.Model):
    QUESTION_TYPES = [
        ('text', 'Текст'),
        ('single_choice', 'Одиночный выбор'),
        ('multi_choice', 'Множественный выбор'),
        ('checkbox', 'Чекбоксы'),
        ('dropdown', 'Выпадающий список'),
        ('likert', 'Шкала Лайкерта'),
        ('rating', 'Рейтинг'),
        ('date_time', 'Дата/время'),
    ]

    question_id = models.AutoField(primary_key=True)
    text_question = models.TextField()
    type_question = models.CharField(max_length=50, choices=QUESTION_TYPES, default='text')
    extra_data = models.JSONField(encoder=DjangoJSONEncoder, null=True, blank=True)

    class Meta:
        db_table = 'questions'
        managed = True


class SurveyQuestions(models.Model):
    survey_question_id = models.AutoField(primary_key=True)
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE, related_name='survey_questions')
    question = models.ForeignKey(Questions, on_delete=models.CASCADE, related_name='survey_questions')
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'survey_questions'
        managed = True
        unique_together = ('survey', 'question')


class RespondentAnswers(models.Model):
    answer_id = models.AutoField(primary_key=True)
    survey_question = models.ForeignKey(SurveyQuestions, on_delete=models.CASCADE, related_name='answers')
    respondent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text_answer = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'respondent_answers'
        managed = True
        unique_together = ('survey_question', 'respondent')


class SurveyArchive(models.Model):
    """
    Архивные опросы (копия опроса + связка с пользователем).
    """
    archive_id = models.AutoField(primary_key=True)
    survey = models.OneToOneField(Surveys, on_delete=models.CASCADE, related_name="archived_copy")
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "survey_archive"
        managed = True
