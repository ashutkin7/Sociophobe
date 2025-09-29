from rest_framework import serializers
from .models import Surveys, Questions, SurveyQuestions, RespondentAnswers
from django.utils import timezone

class SurveyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'date_finished', 'max_residents', 'status']
        read_only_fields = ['survey_id', 'status']

class SurveyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'creator', 'date_finished', 'max_residents', 'status']

class SurveyUpdateSerializer(serializers.ModelSerializer):
    """Для PUT /api/surveys/{survey_id}/"""
    class Meta:
        model = Surveys
        fields = ['name', 'date_finished', 'max_residents']

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questions
        fields = ['question_id', 'text_question', 'type_question']

class QuestionUpdateSerializer(serializers.ModelSerializer):
    """PUT /api/surveys/questions/{question_id}/"""
    class Meta:
        model = Questions
        fields = ['text_question', 'type_question']

class SurveyQuestionLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestions
        fields = ['survey_question_id', 'survey', 'question', 'order']
        read_only_fields = ['survey_question_id']

class RespondentAnswerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RespondentAnswers
        fields = ['answer_id', 'survey_question', 'text_answer']
        read_only_fields = ['answer_id']

    def validate(self, data):
        user = self.context['request'].user
        survey_question = data['survey_question']

        if not getattr(user, 'is_profile_complete', False):
            raise serializers.ValidationError("Profile incomplete — cannot participate in surveys.")

        survey = survey_question.survey
        if not survey.is_active():
            raise serializers.ValidationError("Survey is not active or already finished.")

        if survey.max_residents:
            respondents_count = RespondentAnswers.objects.filter(
                survey_question__survey=survey
            ).values('respondent').distinct().count()
            if respondents_count >= survey.max_residents:
                already_answered = RespondentAnswers.objects.filter(
                    survey_question__survey=survey, respondent=user
                ).exists()
                if not already_answered:
                    raise serializers.ValidationError("Survey reached max participants.")
        if RespondentAnswers.objects.filter(survey_question=survey_question, respondent=user).exists():
            raise serializers.ValidationError("You already answered this question.")
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        ans = RespondentAnswers.objects.create(
            survey_question=validated_data['survey_question'],
            respondent=user,
            text_answer=validated_data.get('text_answer', '')
        )
        return ans
