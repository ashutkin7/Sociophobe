from rest_framework import serializers
from .models import Analytics, Dashboards, AnswerReliability
from surveys.models import Surveys, Questions
from accounts.models import Users
from surveys.models import RespondentSurveyStatus

class AnalyticsSerializer(serializers.ModelSerializer):
    survey_name = serializers.CharField(source='survey.name', read_only=True)
    question_text = serializers.CharField(source='question.text_question', read_only=True)

    class Meta:
        model = Analytics
        fields = [
            'analytics_id',
            'survey',
            'survey_name',
            'question',
            'question_text',
            'type_diagram',
            'title',
            'data_diagram',
            'updated_at'
        ]


class DashboardSerializer(serializers.ModelSerializer):
    survey_name = serializers.CharField(source='survey.name', read_only=True)
    creator_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = Dashboards
        fields = [
            'dashboard_id',
            'survey',
            'survey_name',
            'name',
            'layout',
            'creator_name',
            'created_at',
            'updated_at'
        ]


class SurveySummarySerializer(serializers.Serializer):
    """
    Сводная статистика по опросу.
    """
    total_respondents = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    average_score = serializers.FloatField(allow_null=True)
    top_questions = serializers.ListField(child=serializers.DictField())

class AnswerReliabilitySerializer(serializers.ModelSerializer):
    respondent_email = serializers.EmailField(source="respondent.email", read_only=True)
    survey_name = serializers.CharField(source="survey.name", read_only=True)

    class Meta:
        model = AnswerReliability
        fields = ['id', 'survey', 'survey_name', 'respondent_email', 'reliability_score', 'is_reliable', 'analyzed_at']


class RespondentSurveyStatusScoreSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления score"""
    survey_name = serializers.CharField(source='survey.name', read_only=True)
    respondent_email = serializers.EmailField(source='respondent.email', read_only=True)

    class Meta:
        model = RespondentSurveyStatus
        fields = ['id', 'survey_name', 'respondent_email', 'status', 'score', 'updated_at']
        read_only_fields = ['id', 'updated_at']