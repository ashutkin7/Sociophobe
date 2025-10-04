from rest_framework import serializers
from .models import Surveys, Questions, SurveyQuestions, RespondentAnswers, SurveyArchive
from django.utils import timezone

class SurveyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'date_finished', 'max_residents', 'status', 'type_survey']
        read_only_fields = ['survey_id', 'status']


class SurveyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'creator', 'date_finished', 'max_residents', 'status', 'type_survey']


class SurveyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['name', 'date_finished', 'max_residents', 'type_survey']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questions
        fields = ['question_id', 'text_question', 'type_question', 'extra_data']


class QuestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questions
        fields = ['text_question', 'type_question', 'extra_data']


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
        survey = survey_question.survey

        if not survey.is_active():
            raise serializers.ValidationError("Survey is not active or already finished.")

        if RespondentAnswers.objects.filter(survey_question=survey_question, respondent=user).exists():
            raise serializers.ValidationError("You already answered this question.")

        # --- безопасное чтение extra_data ---
        question = survey_question.question
        extra = question.extra_data

        if not extra:
            extra = {}
        elif isinstance(extra, str):
            import json
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}

        # --- валидация по типу ---
        if question.type_question in ['single_choice', 'multi_choice', 'checkbox', 'dropdown']:
            allowed = extra.get('options', [])
            if allowed and data['text_answer'] not in allowed:
                raise serializers.ValidationError("Invalid choice.")

        if question.type_question == 'likert':
            divisions = extra.get('divisions', 5)
            try:
                val = int(data['text_answer'])
            except (ValueError, TypeError):
                raise serializers.ValidationError("Answer must be integer.")
            if not (1 <= val <= divisions):
                raise serializers.ValidationError("Invalid scale value.")

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        return RespondentAnswers.objects.create(
            survey_question=validated_data['survey_question'],
            respondent=user,
            text_answer=validated_data.get('text_answer', '')
        )

class SurveyArchiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyArchive
        fields = ['archive_id', 'survey', 'archived_at']
