from django.db import models

from surveys.models import Surveys, Questions
from accounts.models import Characteristics



class SurveyRequiredCharacteristics(models.Model):
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE, related_name='required_characteristics')
    characteristic = models.ForeignKey(Characteristics, on_delete=models.CASCADE, related_name='linked_surveys')
    requirements = models.TextField(blank=True, null=True, help_text="Дополнительные условия для характеристики")

    class Meta:
        db_table = 'survey_required_characteristics'
        unique_together = ('survey', 'characteristic')
        verbose_name = "Требуемая характеристика опроса"
        verbose_name_plural = "Требуемые характеристики опросов"

    def __str__(self):
        return f"{self.survey.name} → {self.characteristic.name}"
