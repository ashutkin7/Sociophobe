from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer

from .AI_generate import (
    generate_questions,
    check_question_bias,
    evaluate_reliability,
    detect_anomalies,
    summarize_text
)
from .serializers import (
    GenerateQuestionsSerializer,
    CheckBiasSerializer,
    EvaluateReliabilitySerializer,
    DetectAnomaliesSerializer,
    SummarizeTextSerializer
)

# Отдельная папка (tag) в Swagger
tag = ['Искусственный интеллект']


class GenerateQuestions(APIView):
    @extend_schema(
        summary="Генерация вопросов",
        description=(
            "Генерирует список открытых вопросов по заданной теме. "
            "Используется LLM, возвращает JSON со списком строк."
        ),
        request=GenerateQuestionsSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='GenerateQuestionsResponse',
                    fields={'questions': serializers.ListField(
                        child=serializers.CharField(),
                        help_text="Сгенерированные вопросы")}
                ),
                description="Список вопросов успешно сгенерирован"
            ),
            400: OpenApiResponse(description="Ошибки валидации входных данных")
        },
        tags=tag
    )
    def post(self, request):
        serializer = GenerateQuestionsSerializer(data=request.data)
        if serializer.is_valid():
            topic = serializer.validated_data['topic']
            num = serializer.validated_data['num_questions']
            result = generate_questions(topic, num)
            return Response({"questions": result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckBias(APIView):
    @extend_schema(
        summary="Проверка вопросов на предвзятость",
        description=(
            "Проверяет список вопросов на наличие формулировок, "
            "которые могут стимулировать респондентов давать ложные ответы."
        ),
        request=CheckBiasSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='CheckBiasResponse',
                    fields={'biased_questions_indices': serializers.ListField(
                        child=serializers.IntegerField(),
                        help_text="Индексы вопросов с предвзятыми формулировками")}
                ),
                description="Проверка завершена успешно"
            ),
            400: OpenApiResponse(description="Ошибки валидации входных данных")
        },
        tags=tag
    )
    def post(self, request):
        serializer = CheckBiasSerializer(data=request.data)
        if serializer.is_valid():
            result = check_question_bias(serializer.validated_data['questions'])
            return Response({"biased_questions_indices": result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EvaluateReliability(APIView):
    @extend_schema(
        summary="Оценка достоверности ответов",
        description=(
            "LLM анализирует массив текстовых ответов и возвращает массив "
            "из 0 и 1: 1 — ответ достоверный, 0 — сомнительный."
        ),
        request=EvaluateReliabilitySerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='EvaluateReliabilityResponse',
                    fields={'reliability_scores': serializers.ListField(
                        child=serializers.IntegerField(),
                        help_text="0 — ответ сомнительный, 1 — достоверный")}
                ),
                description="Оценка достоверности выполнена"
            ),
            400: OpenApiResponse(description="Ошибки валидации входных данных")
        },
        tags=tag
    )
    def post(self, request):
        serializer = EvaluateReliabilitySerializer(data=request.data)
        if serializer.is_valid():
            result = evaluate_reliability(serializer.validated_data['answers'])
            return Response({"reliability_scores": result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DetectAnomalies(APIView):
    @extend_schema(
        summary="Выявление аномалий в ответах",
        description=(
            "Определяет индексы аномальных или подозрительных ответов "
            "относительно заданного вопроса."
        ),
        request=DetectAnomaliesSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='DetectAnomaliesResponse',
                    fields={'anomaly_indices': serializers.ListField(
                        child=serializers.IntegerField(),
                        help_text="Индексы аномальных ответов")}
                ),
                description="Аномальные ответы успешно определены"
            ),
            400: OpenApiResponse(description="Ошибки валидации входных данных")
        },
        tags=tag
    )
    def post(self, request):
        serializer = DetectAnomaliesSerializer(data=request.data)
        if serializer.is_valid():
            question = serializer.validated_data['question']
            answers = serializer.validated_data['answers']
            result = detect_anomalies(question, answers)
            return Response({"anomaly_indices": result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SummarizeText(APIView):
    @extend_schema(
        summary="Суммаризация ответов",
        description=(
            "Создаёт сводный объединённый ответ, который отражает "
            "большинство мнений респондентов."
        ),
        request=SummarizeTextSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='SummarizeTextResponse',
                    fields={'summary': serializers.CharField(
                        help_text="Сводный текстовый ответ")}
                ),
                description="Суммаризация выполнена успешно"
            ),
            400: OpenApiResponse(description="Ошибки валидации входных данных")
        },
        tags=tag
    )
    def post(self, request):
        serializer = SummarizeTextSerializer(data=request.data)
        if serializer.is_valid():
            result = summarize_text(serializer.validated_data['answers'])
            return Response({"summary": result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
