from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class AIApiEndpointsTest(APITestCase):
    """
    Автоматическая проверка всех эндпоинтов раздела 'Искусственный интеллект'.
    Использует встроенный тестовый клиент DRF.
    """

    def test_generate_questions(self):
        """Генерация вопросов по теме"""
        url = reverse('generate-questions')
        data = {"topic": "Доставка еды", "num_questions": 5}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("questions", response.data)
        self.assertIsInstance(response.data["questions"], list)

    def test_check_bias(self):
        """Проверка вопросов на предвзятость"""
        url = reverse('check-bias')
        data = {
            "questions": [
                "Знаете ли вы про нашу акцию?",
                "Как вы оцениваете сервис доставки?"
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("biased_questions_indices", response.data)
        self.assertIsInstance(response.data["biased_questions_indices"], list)
        # каждый элемент – индекс (int)
        self.assertTrue(all(isinstance(i, int) for i in response.data["biased_questions_indices"]))

    def test_evaluate_reliability(self):
        """Оценка достоверности массива ответов"""
        url = reverse('evaluate-reliability')
        data = {
            "answers": [
                "Еда пришла вовремя и была горячей.",
                "Все понравилось.",
                "Не знаю."
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("reliability_scores", response.data)
        self.assertIsInstance(response.data["reliability_scores"], list)
        # 0 или 1 для каждого ответа
        self.assertTrue(all(score in [0, 1] for score in response.data["reliability_scores"]))

    def test_detect_anomalies(self):
        """Выявление аномальных ответов относительно вопроса"""
        url = reverse('detect-anomalies')
        data = {
            "question": "Что вам понравилось в сервисе?",
            "answers": [
                "Все понравилось",
                "Быстрая доставка",
                "abrakadabra random words!!!"
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("anomaly_indices", response.data)
        self.assertIsInstance(response.data["anomaly_indices"], list)
        self.assertTrue(all(isinstance(i, int) for i in response.data["anomaly_indices"]))

    def test_summarize_text(self):
        """Суммаризация набора ответов"""
        url = reverse('summarize-text')
        data = {
            "answers": [
                "Еда была вкусная и горячая.",
                "Доставка пришла быстро.",
                "Курьер был вежлив."
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("summary", response.data)
        self.assertIsInstance(response.data["summary"], str)
