from rest_framework import serializers


class GenerateQuestionsSerializer(serializers.Serializer):
    topic = serializers.CharField(help_text="Тема опроса")
    num_questions = serializers.IntegerField(min_value=1, max_value=50, help_text="Количество вопросов")
    double_questions = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Если True — генерирует пары вопросов с одинаковым смыслом"
    )


class CheckBiasSerializer(serializers.Serializer):
    questions = serializers.ListField(
        child=serializers.CharField(),
        help_text="Список вопросов для проверки на предвзятость"
    )


class EvaluateReliabilitySerializer(serializers.Serializer):
    answers = serializers.ListField(
        child=serializers.CharField(),
        help_text="Список текстовых ответов для оценки достоверности"
    )


class DetectAnomaliesSerializer(serializers.Serializer):
    question = serializers.CharField(help_text="Вопрос, относительно которого проверяются ответы")
    answers = serializers.ListField(
        child=serializers.CharField(),
        help_text="Список текстовых ответов"
    )


class SummarizeTextSerializer(serializers.Serializer):
    answers = serializers.ListField(
        child=serializers.CharField(),
        help_text="Список текстовых ответов для суммаризации"
    )

class EvaluateAnswerQualitySerializer(serializers.Serializer):
    questions = serializers.ListField(
        child=serializers.CharField(),
        help_text="Список вопросов, на которые были даны ответы"
    )
    answers = serializers.ListField(
        child=serializers.CharField(),
        help_text="Список ответов в том же порядке, что и вопросы"
    )
