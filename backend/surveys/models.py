from django.db import models
from django.conf import settings

class Surveys(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('stopped', 'Stopped'),
        ('finished', 'Finished'),
    ]

    survey_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_finished = models.DateTimeField(null=True, blank=True)
    max_residents = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    class Meta:
        db_table = 'surveys'
        managed = True

    def is_active(self):
        from django.utils import timezone
        if self.status != 'active':
            return False
        if self.date_finished and timezone.now() > self.date_finished:
            return False
        return True


class Questions(models.Model):
    question_id = models.AutoField(primary_key=True)
    text_question = models.TextField()
    # optionally add question type field
    type_question = models.CharField(max_length=50, default='text')  # 'text', 'single_choice', 'multi_choice', etc.

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
