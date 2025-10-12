import json
import traceback
from django.conf import settings
from rest_framework import serializers
from .models import Surveys, Questions, SurveyQuestions, RespondentAnswers, SurveyArchive, RespondentSurveyStatus
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import RespondentAnswers
from core.models import SurveyRequiredCharacteristics


def log_validation_error(serializer_name: str, field_name: str, data, error):
    """Утилита для красивого вывода ошибок в консоль"""
    print("\n" + "=" * 80)
    print(f"❌ [VALIDATION ERROR] в сериализаторе: {serializer_name}")
    if field_name:
        print(f"🔹 Поле: {field_name}")
    print(f"🔹 Ошибка: {error}")
    print(f"🔹 Данные: {json.dumps(data, ensure_ascii=False, indent=2)}")
    print("-" * 80)
    traceback.print_exc()
    print("=" * 80 + "\n")


class SurveyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'date_finished', 'max_residents', 'status', 'type_survey', 'cost']
        read_only_fields = ['survey_id', 'status']


class SurveyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'creator', 'date_finished', 'max_residents', 'status', 'type_survey', 'cost']


class SurveyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['name', 'date_finished', 'max_residents', 'type_survey', 'cost']

# === QUESTIONS ===
class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questions
        fields = ['question_id', 'text_question', 'type_question', 'extra_data']


class QuestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questions
        fields = ['text_question', 'type_question', 'extra_data']

    def validate(self, data):
        serializer_name = self.__class__.__name__
        type_question = data.get('type_question', getattr(self.instance, 'type_question', None))
        extra = data.get('extra_data', getattr(self.instance, 'extra_data', {}))

        # --- Безопасное чтение JSON ---
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception as e:
                log_validation_error(serializer_name, "extra_data", data, f"Ошибка парсинга JSON: {e}")
                raise serializers.ValidationError({"extra_data": "Некорректный JSON формат."})

        if not isinstance(extra, dict):
            log_validation_error(serializer_name, "extra_data", data, "extra_data не является объектом (dict)")
            raise serializers.ValidationError({"extra_data": "extra_data должно быть объектом (dict)."})

        # --- Проверяем структуру по типу вопроса ---
        try:
            if type_question in ['single_choice', 'multi_choice', 'checkbox', 'dropdown']:
                options = extra.get('options')
                if not isinstance(options, list) or not all(isinstance(x, str) for x in options):
                    raise serializers.ValidationError(
                        {"extra_data": "Для выбора вариантов нужен список строк 'options'."}
                    )

            elif type_question == 'likert':
                scale = extra.get('scale')
                if not isinstance(scale, int) or scale < 2:
                    raise serializers.ValidationError({"extra_data": "Поле 'scale' должно быть целым числом ≥ 2."})
                if 'min_label' not in extra or 'max_label' not in extra:
                    raise serializers.ValidationError({"extra_data": "Укажите поля 'min_label' и 'max_label'."})

            elif type_question == 'number':
                min_val = extra.get('min')
                max_val = extra.get('max')
                if min_val is not None and not isinstance(min_val, (int, float)):
                    raise serializers.ValidationError({"extra_data": "Поле 'min' должно быть числом."})
                if max_val is not None and not isinstance(max_val, (int, float)):
                    raise serializers.ValidationError({"extra_data": "Поле 'max' должно быть числом."})

            elif type_question == 'date':
                if 'format' in extra and not isinstance(extra['format'], str):
                    raise serializers.ValidationError({"extra_data": "Поле 'format' должно быть строкой."})

        except serializers.ValidationError as e:
            # Логируем именно текст ошибки
            log_validation_error(serializer_name, "extra_data", data, e.detail)
            raise
        except Exception as e:
            log_validation_error(serializer_name, "extra_data", data, f"Неожиданная ошибка: {e}")
            raise serializers.ValidationError({"extra_data": f"Неожиданная ошибка: {str(e)}"})

        data['extra_data'] = extra
        return data


# === LINKING ===
class SurveyQuestionLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestions
        fields = ['survey_question_id', 'survey', 'question', 'order']
        read_only_fields = ['survey_question_id']


# === RESPONDENT ANSWERS ===
class RespondentAnswerCreateSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = RespondentAnswers
        fields = ['answer_id', 'question_id', 'text_answer']
        read_only_fields = ['answer_id']

    def validate(self, data):
        serializer_name = self.__class__.__name__
        try:
            user = self.context['request'].user
            question_id = data.get('question_id')

            # --- ищем вопрос и связь ---
            question = get_object_or_404(Questions, pk=question_id)
            link = SurveyQuestions.objects.filter(question=question).select_related('survey').first()
            if not link:
                raise serializers.ValidationError("Этот вопрос не привязан ни к одному опросу.")

            survey = link.survey
            if not survey.is_active():
                raise serializers.ValidationError("Опрос не активен или завершён.")

            # --- проверяем extra_data для типа вопроса ---
            extra = question.extra_data or {}
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = {}

            # === Дополнительная валидация значения ===
            text_answer = data.get("text_answer")

            # if question.type_question in ['single_choice', 'multi_choice', 'checkbox', 'dropdown']:
            #     allowed = extra.get('options', [])
            #     if allowed and text_answer not in allowed:
            #         raise serializers.ValidationError("Недопустимый вариант ответа.")
            #
            # elif question.type_question == 'likert':
            #     divisions = extra.get('scale', 5)
            #     try:
            #         val = int(text_answer)
            #     except (ValueError, TypeError):
            #         raise serializers.ValidationError("Ответ должен быть числом.")
            #     if not (1 <= val <= divisions):
            #         raise serializers.ValidationError("Значение вне допустимого диапазона шкалы.")
            #
            # elif question.type_question == 'number':
            #     try:
            #         val = float(text_answer)
            #     except (ValueError, TypeError):
            #         raise serializers.ValidationError("Ответ должен быть числом.")
            #     min_val = extra.get('min')
            #     max_val = extra.get('max')
            #     if min_val is not None and val < min_val:
            #         raise serializers.ValidationError(f"Минимальное значение: {min_val}.")
            #     if max_val is not None and val > max_val:
            #         raise serializers.ValidationError(f"Максимальное значение: {max_val}.")
            #
            # elif question.type_question == 'date':
            #     # Можно добавить проверку формата, если задан
            #     pass

            # --- сохраняем объект связи ---
            data['survey_question'] = link
            data['respondent'] = user

            return data

        except Exception as e:
            log_validation_error(serializer_name, "text_answer", data, e)
            raise

    def create(self, validated_data):
        user = validated_data['respondent']
        survey_question = validated_data['survey_question']
        text_answer = validated_data.get('text_answer', '')

        # --- если ответ уже существует — обновляем ---
        existing = RespondentAnswers.objects.filter(
            survey_question=survey_question,
            respondent=user
        ).first()

        if existing:
            existing.text_answer = text_answer
            existing.save()
            print(f"🔁 Обновлён ответ пользователя {user} на вопрос {survey_question.question_id}")
            return existing

        # --- иначе создаём новый ---
        answer = RespondentAnswers.objects.create(
            survey_question=survey_question,
            respondent=user,
            text_answer=text_answer
        )
        print(f"✅ Создан новый ответ пользователя {user} на вопрос {survey_question.question_id}")
        return answer



class SurveyArchiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyArchive
        fields = ['archive_id', 'survey', 'archived_at']

class RespondentSurveyStatusSerializer(serializers.ModelSerializer):
    survey_name = serializers.CharField(source='survey.name', read_only=True)

    class Meta:
        model = RespondentSurveyStatus
        fields = ['id', 'survey', 'survey_name', 'status', 'score', 'updated_at']
        read_only_fields = ['id', 'updated_at']

class RespondentAnswerDetailSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source='survey_question.question.question_id', read_only=True)
    question_text = serializers.CharField(source='survey_question.question.text_question', read_only=True)
    type_question = serializers.CharField(source='survey_question.question.type_question', read_only=True)

    class Meta:
        model = RespondentAnswers
        fields = [
            'answer_id',
            'question_id',
            'question_text',
            'type_question',
            'text_answer',
            'created_at',
        ]

# --- ХАРАКТЕРИСТИКИ ДЛЯ ОПРОСА ---

class SurveyRequiredCharacteristicSerializer(serializers.ModelSerializer):
    characteristic_name = serializers.CharField(source='characteristic.name', read_only=True)

    class Meta:
        model = SurveyRequiredCharacteristics
        fields = ['id', 'survey', 'characteristic', 'characteristic_name', 'requirements']