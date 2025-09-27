from rest_framework import serializers

class GenerateQuestionsSerializer(serializers.Serializer):
    topic = serializers.CharField(help_text="Тема опроса")
    num_questions = serializers.IntegerField(min_value=1, max_value=50, help_text="Количество вопросов")

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
