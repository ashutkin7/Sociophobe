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

    # ✅ Новое поле
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Стоимость (или вознаграждение) за прохождение опроса"
    )

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

class RespondentSurveyStatus(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'В процессе'),
        ('completed', 'Пройден'),
    ]

    id = models.AutoField(primary_key=True)
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='survey_statuses'
    )
    survey = models.ForeignKey(
        Surveys,
        on_delete=models.CASCADE,
        related_name='respondent_statuses'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Оценка качества прохождения опроса (0.0–1.0)"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'respondent_survey_status'
        managed = True
        unique_together = ('respondent', 'survey')

    def __str__(self):
        return f"{self.respondent} — {self.survey.name}: {self.status} ({self.score if self.score is not None else 'нет оценки'})"
