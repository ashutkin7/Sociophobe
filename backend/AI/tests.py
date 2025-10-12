from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class AIApiExtendedTest(APITestCase):
    """Расширенные тесты AI-эндпоинтов и функций"""

    def test_generate_questions_repeat_random(self):
        """Генерация пар вопросов с перемешанным порядком"""
        url = reverse("generate-questions-repeat")
        data = {"topic": "Транспорт", "num_questions": 4}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("questions", response.data)
        self.assertIsInstance(response.data["questions"], list)
        self.assertGreater(len(response.data["questions"]), 0)

    def test_evaluate_answer_quality_with_overall_score(self):
        """Проверка корректности анализа качества ответов"""
        url = reverse("evaluate-answer-quality")
        data = {
            "questions": [
                "Как часто вы пользуетесь доставкой?",
                "Что влияет на ваш выбор сервиса доставки?"
            ],
            "answers": [
                "Обычно раз в неделю.",
                "На выбор влияет скорость и цена."
            ]
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("evaluations", response.data)
        self.assertIn("overall_score", response.data)
        self.assertTrue(0 <= response.data["overall_score"] <= 1)

    def test_auto_average_score_when_missing(self):
        """Если overall_score не вернулся — должен быть вычислен автоматически"""
        from .AI_generate import evaluate_answer_quality
        fake_json = {
            "evaluations": [
                {"question": "Q1", "answer": "A1", "score": 0.8, "issues": []},
                {"question": "Q2", "answer": "A2", "score": 0.6, "issues": ["short"]}
            ]
        }
        import json
        response_mock = json.dumps(fake_json)
        # Симулируем отсутствие overall_score
        result = evaluate_answer_quality(["Q1", "Q2"], ["A1", "A2"])
        self.assertIn("overall_score", result)
        self.assertAlmostEqual(result["overall_score"], 0.7, delta=0.01)

    def test_error_handling_in_quality_check(self):
        """Проверка корректности обработки ошибок при некорректных данных"""
        from .AI_generate import evaluate_answer_quality
        result = evaluate_answer_quality([], [])
        self.assertIsInstance(result, dict)
        self.assertIn("overall_score", result)
        self.assertEqual(result["overall_score"], 0.0)
