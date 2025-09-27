from django.urls import path
from .views import (
    GenerateQuestions,
    CheckBias,
    EvaluateReliability,
    DetectAnomalies,
    SummarizeText
)

urlpatterns = [
    path('generate-questions/', GenerateQuestions.as_view(), name='generate-questions'),
    path('check-bias/', CheckBias.as_view(), name='check-bias'),
    path('evaluate-reliability/', EvaluateReliability.as_view(), name='evaluate-reliability'),
    path('detect-anomalies/', DetectAnomalies.as_view(), name='detect-anomalies'),
    path('summarize-text/', SummarizeText.as_view(), name='summarize-text'),
]
