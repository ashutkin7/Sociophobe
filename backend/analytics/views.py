import pandas as pd
from io import BytesIO
import requests
import re
import time
from collections import Counter
from statistics import mean, median
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import is_aware
from django.db.models import Avg, Count, FloatField
from django.db.models.functions import Cast

from rest_framework import permissions, serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiResponse,
    OpenApiParameter
)

from surveys.models import (
    Surveys, RespondentSurveyStatus, RespondentAnswers, SurveyQuestions
)
from accounts.models import RespondentCharacteristics


# ==========================================================
# 🔹 1. Anonymized Data View — Получение обезличенных ответов
# ==========================================================
class AnonymizedDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="📄 Получение обезличенных ответов опроса",
        description=(
            "Возвращает таблицу, где каждая строка — это один респондент. "
            "Столбцы содержат email, оценку, дату завершения и ответы на все вопросы."
        ),
        tags=["Аналитика"],
        parameters=[
            OpenApiParameter(
                name="survey_id",
                description="ID опроса для выборки ответов.",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Успешное получение обезличенных ответов.",
                response=inline_serializer(
                    name="AnonymizedDataResponse",
                    fields={
                        "email": serializers.EmailField(),
                        "score": serializers.FloatField(),
                        "completed_at": serializers.DateTimeField(),
                        "question_text": serializers.CharField(help_text="Ответ респондента на вопрос"),
                    }
                ),
            ),
            404: OpenApiResponse(description="Опрос не найден")
        }
    )
    def get(self, request, survey_id: int):
        survey = get_object_or_404(Surveys, pk=survey_id)
        statuses = RespondentSurveyStatus.objects.filter(survey=survey, status="completed")
        questions = SurveyQuestions.objects.filter(survey=survey).select_related("question").order_by("order")

        data_rows = []
        for status in statuses:
            respondent_answers = RespondentAnswers.objects.filter(
                respondent=status.respondent, survey_question__survey=survey
            ).select_related("survey_question__question")

            row = {
                "email": status.respondent.email,
                "score": status.score,
                "completed_at": status.updated_at,
            }

            for sq in questions:
                answer_obj = next((a for a in respondent_answers if a.survey_question == sq), None)
                row[sq.question.text_question] = answer_obj.text_answer if answer_obj else ""

            data_rows.append(row)

        df = pd.DataFrame(data_rows)
        return JsonResponse(df.to_dict(orient="records"), safe=False)


# ==========================================================
# 🔹 2. Export Data View — Экспорт данных
# ==========================================================
class ExportDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="📤 Экспорт данных опроса (CSV или XLSX)",
        description=(
            "Позволяет выгрузить все данные опроса в формате CSV или Excel.\n\n"
            "**Поля:** email, оценка, дата завершения и ответы на все вопросы."
        ),
        request=inline_serializer(
            name="ExportRequest",
            fields={
                "format": serializers.ChoiceField(
                    choices=["csv", "xlsx"],
                    help_text="Формат экспорта. По умолчанию — CSV.",
                    default="csv",
                )
            },
        ),
        responses={
            200: OpenApiResponse(description="Файл успешно сгенерирован"),
            404: OpenApiResponse(description="Опрос не найден"),
        },
        tags=["Аналитика"],
    )
    def post(self, request, survey_id: int):
        fmt = request.data.get("format", "csv")
        survey = get_object_or_404(Surveys, pk=survey_id)

        statuses = RespondentSurveyStatus.objects.filter(survey=survey, status="completed")
        questions = SurveyQuestions.objects.filter(survey=survey).select_related("question").order_by("order")

        data_rows = []
        for status in statuses:
            respondent_answers = RespondentAnswers.objects.filter(
                respondent=status.respondent, survey_question__survey=survey
            ).select_related("survey_question__question")

            row = {
                "email": status.respondent.email,
                "score": status.score,
                "completed_at": status.updated_at.replace(tzinfo=None)
                if is_aware(status.updated_at)
                else status.updated_at,
            }

            for sq in questions:
                answer_obj = next((a for a in respondent_answers if a.survey_question == sq), None)
                row[sq.question.text_question] = answer_obj.text_answer if answer_obj else ""

            data_rows.append(row)

        df = pd.DataFrame(data_rows)

        if fmt == "xlsx":
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            buffer.seek(0)
            response = HttpResponse(
                buffer,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="survey_{survey_id}.xlsx"'
        else:
            csv_data = df.to_csv(index=False)
            response = HttpResponse(csv_data, content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="survey_{survey_id}.csv"'

        return response


# ==========================================================
# 🔹 3. Dashboard Data View — Аналитика ответов
#   Изменения:
#   - rating: добавлены все значения и среднее
#   - date_time: добавлены все значения + распределение
#   - text: ожидание ответа AI с повторами и таймаутами
# ==========================================================
class DashboardDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="📊 Дашборд анализа ответов",
        description=(
            "Возвращает сводную статистику по всем вопросам опроса.\n\n"
            "- Выборочные: распределение ответов\n"
            "- Рейтинговые: список всех значений и среднее\n"
            "- Даты/время: список всех значений и распределение\n"
            "- Текстовые: суммаризация через AI `/api/AI/summarize-text/` с ожиданием ответа"
        ),
        tags=["Аналитика"],
        parameters=[
            OpenApiParameter(
                name="survey_id", description="ID опроса", required=True, type=int, location=OpenApiParameter.PATH
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Успешное получение дашборда",
                response=inline_serializer(
                    name="DashboardResponse",
                    fields={
                        "survey_id": serializers.IntegerField(),
                        "dashboard": serializers.DictField(help_text="Детальная аналитика по вопросам"),
                    },
                ),
            )
        },
    )
    def get(self, request, survey_id: int):
        survey = get_object_or_404(Surveys, pk=survey_id)
        questions = SurveyQuestions.objects.filter(survey=survey).select_related("question").order_by("order")

        dashboard_data = {}

        for sq in questions:
            q = sq.question
            answers = RespondentAnswers.objects.filter(survey_question=sq)

            if not answers.exists():
                continue

            if q.type_question in ["single_choice", "multi_choice", "dropdown"]:
                distribution = answers.values("text_answer").annotate(count=Count("text_answer"))
                total = sum(item["count"] for item in distribution)
                for item in distribution:
                    item["percent"] = round(item["count"] / total * 100, 2)
                dashboard_data[q.text_question] = {
                    "type": q.type_question,
                    "distribution": list(distribution),
                }

            elif q.type_question == "rating":
                raw_vals = list(answers.values_list("text_answer", flat=True))
                nums = []
                for v in raw_vals:
                    try:
                        nums.append(float(v))
                    except Exception:
                        continue
                avg_value = round(mean(nums), 4) if nums else None
                dashboard_data[q.text_question] = {
                    "type": "rating",
                    "values": nums,
                    "average": avg_value,
                }

            elif q.type_question == "date_time":
                raw_vals = list(answers.values_list("text_answer", flat=True))
                distribution = answers.values("text_answer").annotate(count=Count("text_answer"))
                dashboard_data[q.text_question] = {
                    "type": "date_time",
                    "values": raw_vals,
                    "distribution": list(distribution),
                }

            else:
                text_list = [a.text_answer for a in answers if a.text_answer]
                if text_list:
                    summary = ""
                    try:
                        ai_url = f"{request.scheme}://{request.get_host()}/api/AI/summarize-text/"
                        # Повторы с экспоненциальной задержкой и раздельными таймаутами (connect/read)
                        # timeout=(connect_timeout, read_timeout)
                        attempts = 5
                        for i in range(attempts):
                            resp = requests.post(ai_url, json={"answers": text_list}, timeout=(5, 30))
                            if resp.status_code == 200:
                                data = resp.json()
                                summary = data.get("summary", "") or ""
                                if summary:
                                    break
                            # бэкофф: 0.5, 1, 2, 3, 3 сек
                            delay = min(3.0, 0.5 * (2 ** i))
                            time.sleep(delay)
                        if not summary:
                            # Фоллбек — ключевые слова, если сервис не дал результат
                            all_text = " ".join(text_list)
                            words = re.findall(r"\w+", all_text.lower())
                            freq = Counter(words)
                            top_words = [w for w, _ in freq.most_common(5)]
                            summary = "Основные темы: " + ", ".join(top_words)
                    except Exception:
                        all_text = " ".join(text_list)
                        words = re.findall(r"\w+", all_text.lower())
                        freq = Counter(words)
                        top_words = [w for w, _ in freq.most_common(5)]
                        summary = "Основные темы: " + ", ".join(top_words)

                else:
                    summary = ""

                dashboard_data[q.text_question] = {"type": "text", "summary": summary}

        return Response({"survey_id": survey_id, "dashboard": dashboard_data})


# ==========================================================
# 🔹 4. Respondent Dashboard View — Аналитика характеристик
#   Изменения:
#   - Возвращаем только количество респондентов и characteristics_summary
#   - Для numeric: полный список значений (values) вместо агрегатов
# ==========================================================
class RespondentDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="👥 Аналитика характеристик респондентов",
        description=(
            "Возвращает только количество респондентов и распределения их характеристик.\n\n"
            "- choice: процентное распределение\n"
            "- numeric: список всех значений"
        ),
        tags=["Аналитика"],
        parameters=[
            OpenApiParameter(
                name="survey_id",
                description="ID опроса, для которого формируется аналитика.",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Успешное получение аналитики характеристик",
                response=inline_serializer(
                    name="RespondentDashboardResponse",
                    fields={
                        "respondents_count": serializers.IntegerField(),
                        "characteristics_summary": serializers.DictField(),
                    },
                ),
            )
        },
    )
    def get(self, request, survey_id: int):
        survey = get_object_or_404(Surveys, pk=survey_id)
        completed = RespondentSurveyStatus.objects.filter(survey=survey, status='completed').select_related('respondent')

        respondents_count = completed.count()
        all_characteristics = {}

        # Сбор значений характеристик
        for st in completed:
            user = st.respondent
            chars = RespondentCharacteristics.objects.filter(user=user).select_related('characteristic_value__characteristic')

            for rc in chars:
                
                characteristic = rc.characteristic_value.characteristic
                value = rc.characteristic_value.value_text
                vtype = characteristic.value_type

                if characteristic.name not in all_characteristics:
                    all_characteristics[characteristic.name] = {"value_type": vtype, "values": []}
                all_characteristics[characteristic.name]["values"].append(value)

        # 🔹 агрегированная аналитика
        characteristics_summary = {}
        for name, data in all_characteristics.items():
            values = [v for v in data["values"] if v is not None]
            vtype = data["value_type"]
            if not values:
                continue

            if vtype in ["choice", "select", "dropdown"]:
                counter = Counter(values)
                total = sum(counter.values())
                dist = [
                    {"value": val, "count": cnt, "percent": round(cnt / total * 100, 2)}
                    for val, cnt in counter.items()
                ]
                characteristics_summary[name] = {"type": "choice", "distribution": dist}

            elif vtype in ["numeric", "number", "int", "float"]:
                nums = []
                for v in values:
                    try:
                        nums.append(float(v))
                    except Exception:
                        continue
                if not nums:
                    continue
                # Возвращаем полный список значений
                characteristics_summary[name] = {
                    "type": "numeric",
                    "values": nums,
                }

        return Response({
            "respondents_count": respondents_count,
            "characteristics_summary": characteristics_summary,
        })
