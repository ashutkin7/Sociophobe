# survey/views.py
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from .serializers import (
    SurveyCreateSerializer, SurveyDetailSerializer, QuestionSerializer,
    SurveyQuestionLinkSerializer, RespondentAnswerCreateSerializer
)
from .models import Surveys, Questions, SurveyQuestions, RespondentAnswers
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from django.utils import timezone
from django.db import models

tag = ['Опросы']

def role_allowed(user, roles):
    """Проверка роли пользователя."""
    return getattr(user, 'role', None) in roles


class SurveyCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Создать опрос",
        description="Создание нового опроса (только для ролей customer или moderator).",
        request=SurveyCreateSerializer,
        responses={201: SurveyDetailSerializer},
        tags=tag
    )
    def post(self, request):
        if not role_allowed(request.user, ['customer', 'moderator']):
            return Response({"detail": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN)
        serializer = SurveyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey = serializer.save(creator=request.user, status='draft')
        return Response(SurveyDetailSerializer(survey).data, status=status.HTTP_201_CREATED)


class MySurveysView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Мои опросы",
        description="Получить список всех опросов, созданных текущим пользователем.",
        responses={200: SurveyDetailSerializer(many=True)},
        tags=tag
    )
    def get(self, request):
        qs = Surveys.objects.filter(creator=request.user)
        return Response(SurveyDetailSerializer(qs, many=True).data, status=status.HTTP_200_OK)


class QuestionCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Создать вопрос",
        description="Добавить новый вопрос в общий пул вопросов (для customer или moderator).",
        request=QuestionSerializer,
        responses={201: inline_serializer(
            name='ИдентификаторВопроса',
            fields={'question_id': serializers.IntegerField()}
        )},
        tags=tag
    )
    def post(self, request):
        if not role_allowed(request.user, ['customer', 'moderator']):
            return Response({"detail": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        q = serializer.save()
        return Response({'question_id': q.question_id}, status=status.HTTP_201_CREATED)


class SurveyQuestionLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Привязать вопрос к опросу",
        description="Привязка существующего вопроса к выбранному опросу (customer/moderator).",
        request=SurveyQuestionLinkSerializer,
        responses={201: inline_serializer(
            name='ИдентификаторПривязки',
            fields={'survey_question_id': serializers.IntegerField()}
        )},
        tags=tag
    )
    def post(self, request):
        if not role_allowed(request.user, ['customer', 'moderator']):
            return Response({"detail": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN)
        serializer = SurveyQuestionLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey = get_object_or_404(Surveys, pk=serializer.validated_data['survey'].survey_id)
        if survey.creator != request.user and request.user.role != 'moderator':
            return Response({"detail": "Нельзя добавлять вопросы в чужой опрос"},
                            status=status.HTTP_403_FORBIDDEN)
        sq = serializer.save()
        return Response({'survey_question_id': sq.survey_question_id}, status=status.HTTP_201_CREATED)


class SurveyQuestionsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Список вопросов опроса",
        description="Получить список всех вопросов, привязанных к конкретному опросу.",
        responses={200: QuestionSerializer(many=True)},
        tags=tag
    )
    def get(self, request, survey_id: int):
        survey = get_object_or_404(Surveys, pk=survey_id)
        qlinks = SurveyQuestions.objects.filter(survey=survey).select_related('question').order_by('order')
        questions = [ql.question for ql in qlinks]
        return Response(QuestionSerializer(questions, many=True).data, status=status.HTTP_200_OK)


class RespondentAnswerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Отправить ответ",
        description="Респондент отправляет ответ на конкретный вопрос выбранного опроса.",
        request=RespondentAnswerCreateSerializer,
        responses={201: inline_serializer(
            name='ИдентификаторОтвета',
            fields={'answer_id': serializers.IntegerField()}
        )},
        tags=tag
    )
    def post(self, request):
        if not role_allowed(request.user, ['respondent']):
            return Response({"detail": "Только респонденты могут отправлять ответы"},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = RespondentAnswerCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        ans = serializer.save()
        return Response({'answer_id': ans.answer_id}, status=status.HTTP_201_CREATED)


class SurveyAnswersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Все ответы на опрос",
        description="Получить полный список ответов респондентов на выбранный опрос "
                    "(доступно только создателю опроса или модератору).",
        responses={200: inline_serializer(
            name='ОтветыОпроса',
            fields={'answers': serializers.ListField(child=serializers.DictField())}
        )},
        tags=tag
    )
    def get(self, request, survey_id: int):
        survey = get_object_or_404(Surveys, pk=survey_id)
        if not (survey.creator == request.user or request.user.role == 'moderator'):
            return Response({"detail": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN)
        answers = RespondentAnswers.objects.filter(
            survey_question__survey=survey
        ).select_related('respondent', 'survey_question', 'survey_question__question')
        out = []
        for a in answers:
            out.append({
                'answer_id': a.answer_id,
                'survey_question_id': a.survey_question.survey_question_id,
                'question_id': a.survey_question.question.question_id,
                'respondent_id': a.respondent.user_id,
                'text_answer': a.text_answer,
                'created_at': a.created_at,
            })
        return Response({'answers': out}, status=status.HTTP_200_OK)


class SurveyToggleStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Изменить статус опроса",
        description="Запуск или остановка опроса: изменение поля статус на одно из "
                    "`draft`, `active`, `stopped`, `finished`. "
                    "Доступно только создателю опроса или модератору.",
        request=inline_serializer(
            name='НовыйСтатус',
            fields={'status': serializers.ChoiceField(
                choices=['draft', 'active', 'stopped', 'finished']
            )}
        ),
        responses={200: inline_serializer(
            name='СтатусОпроса',
            fields={'survey_id': serializers.IntegerField(), 'status': serializers.CharField()}
        )},
        tags=tag
    )
    def post(self, request, survey_id: int):
        survey = get_object_or_404(Surveys, pk=survey_id)
        if not (survey.creator == request.user or request.user.role == 'moderator'):
            return Response({"detail": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN)
        desired_status = request.data.get('status')
        if desired_status not in dict(Surveys.STATUS_CHOICES):
            return Response({"detail": "Недопустимый статус"}, status=status.HTTP_400_BAD_REQUEST)
        survey.status = desired_status
        survey.save()
        return Response({'survey_id': survey.survey_id, 'status': survey.status},
                        status=status.HTTP_200_OK)


class AvailableSurveysView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Доступные опросы для респондента",
        description="Список активных опросов, которые ещё не завершены и не превысили "
                    "максимальное количество респондентов.",
        responses={200: SurveyDetailSerializer(many=True)},
        tags=tag
    )
    def get(self, request):
        now = timezone.now()
        qs = Surveys.objects.filter(status='active').filter(
            models.Q(date_finished__isnull=True) | models.Q(date_finished__gt=now)
        )
        available = []
        for s in qs:
            if s.max_residents:
                respondents_count = RespondentAnswers.objects.filter(
                    survey_question__survey=s
                ).values('respondent').distinct().count()
                if respondents_count >= s.max_residents:
                    continue
            available.append(s)
        return Response(SurveyDetailSerializer(available, many=True).data,
                        status=status.HTTP_200_OK)
