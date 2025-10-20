from django.db import models
from django.conf import settings
from surveys.models import Surveys, Questions

class Analytics(models.Model):
    """
    Хранит агрегированные аналитические данные по вопросам и опросам.
    """
    analytics_id = models.AutoField(primary_key=True)
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE, related_name='analytics')
    question = models.ForeignKey(Questions, on_delete=models.CASCADE, null=True, blank=True, related_name='analytics')
    type_diagram = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    data_diagram = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analytics'
        verbose_name = "Аналитика"
        verbose_name_plural = "Аналитика"

    def __str__(self):
        return f"{self.survey.name} — {self.question.text_question[:50] if self.question else 'Общая аналитика'}"


class Dashboards(models.Model):
    """
    Хранит конфигурации дашбордов (наборы аналитических блоков).
    """
    dashboard_id = models.AutoField(primary_key=True)
    survey = models.OneToOneField(Surveys, on_delete=models.CASCADE, related_name='dashboard')
    name = models.CharField(max_length=255, default="Основной дашборд")
    layout = models.JSONField(default=dict, blank=True, help_text="Структура расположения блоков (chart/table и т.п.)")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_dashboards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dashboards'
        verbose_name = "Дашборд"
        verbose_name_plural = "Дашборды"

    def __str__(self):
        return f"Дашборд для {self.survey.name}"

class AnswerReliability(models.Model):
    """Оценка достоверности ответов респондентов"""
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE)
    respondent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reliability_score = models.FloatField(default=0.0)
    is_reliable = models.BooleanField(default=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'answer_reliability'
        verbose_name = "Оценка достоверности ответа"
        verbose_name_plural = "Оценки достоверности ответов"


class CorrelationAnalysis(models.Model):
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE)
    variable_x = models.CharField(max_length=255)
    variable_y = models.CharField(max_length=255)
    correlation_coefficient = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

class ClusterGroup(models.Model):
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE)
    cluster_label = models.CharField(max_length=100)
    respondent_ids = models.JSONField(default=list)
    keywords = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

