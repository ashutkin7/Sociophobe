from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone
from django.contrib.auth import get_user_model

from surveys.models import Surveys, Questions, SurveyQuestions, RespondentAnswers, RespondentSurveyStatus
from accounts.models import Characteristics, CharacteristicValues, RespondentCharacteristics
from analytics.models import AnswerReliability  # если есть

import json

User = get_user_model()


class AnalyticsEndpointsTest(APITestCase):
    """🔍 Полный интеграционный тест аналитических эндпоинтов"""

    def setUp(self):
        print("\n[SETUP] Создаём тестовые данные для аналитики...")
        self.customer = User.objects.create_user(
            email="customer@example.com", password="pass1234", name="Customer", role="customer"
        )
        self.respondent = User.objects.create_user(
            email="respondent@example.com", password="pass1234", name="Respondent", role="respondent"
        )

        self.client = APIClient()
        self.client.force_authenticate(self.customer)

        # Создаём опрос
        self.survey = Surveys.objects.create(
            name="Тестовый опрос",
            creator=self.customer,
            status="active",
            type_survey="simple",
            cost=10.00
        )

        # Вопросы
        self.q1 = Questions.objects.create(text_question="Как вы оцениваете сервис?", type_question="text")
        self.q2 = Questions.objects.create(text_question="Оцените по шкале 1-5", type_question="rating")

        self.sq1 = SurveyQuestions.objects.create(survey=self.survey, question=self.q1, order=1)
        self.sq2 = SurveyQuestions.objects.create(survey=self.survey, question=self.q2, order=2)

        # Ответы респондента
        RespondentAnswers.objects.create(
            survey_question=self.sq1,
            respondent=self.respondent,
            text_answer="Все отлично"
        )
        RespondentAnswers.objects.create(
            survey_question=self.sq2,
            respondent=self.respondent,
            text_answer="4"
        )

        # Статус (completed)
        RespondentSurveyStatus.objects.create(
            respondent=self.respondent,
            survey=self.survey,
            status="completed",
            score=0.9,
            updated_at=timezone.now()
        )

        # Характеристики
        self.char_gender = Characteristics.objects.create(name="Пол", value_type="choice")
        self.char_age = Characteristics.objects.create(name="Возраст", value_type="numeric")

        self.val_gender = CharacteristicValues.objects.create(characteristic=self.char_gender, value_text="Мужской")
        self.val_age = CharacteristicValues.objects.create(characteristic=self.char_age, value_text="30")

        RespondentCharacteristics.objects.create(
            user=self.respondent, characteristic_value=self.val_gender, score=0.95
        )
        RespondentCharacteristics.objects.create(
            user=self.respondent, characteristic_value=self.val_age, score=0.88
        )

        # Надёжность ответов (если модель есть)
        try:
            AnswerReliability.objects.create(
                survey=self.survey,
                respondent=self.respondent,
                reliability_score=0.93,
                is_reliable=True
            )
        except Exception:
            pass

        print(f"[SETUP] ✅ Данные успешно созданы. survey_id={self.survey.pk}\n")

    # ==============================================================
    # 🔹 1. Анонимизированные данные
    # ==============================================================
    def test_anonymized_data(self):
        print("\n[Test] GET /api/analytics/{survey_id}/anonymized-data/")
        url = reverse('anonymized-data', args=[self.survey.pk])
        response = self.client.get(url)
        print("  -> Status:", response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        print(f"  -> Получено {len(data)} записей")
        self.assertIsInstance(data, list)
        if data:
            first = data[0]
            print("  -> Поля первой строки:", list(first.keys()))
            self.assertIn("email", first)
            self.assertIn("score", first)
            self.assertIn(self.q1.text_question, first)

    # ==============================================================
    # 🔹 2. Экспорт CSV
    # ==============================================================
    def test_export_csv(self):
        print("\n[Test] POST /api/analytics/{survey_id}/export/ (CSV)")
        url = reverse('export-data', args=[self.survey.pk])
        payload = {"format": "csv"}
        response = self.client.post(url, data=payload)
        print("  -> Status:", response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        content_type = response.get('Content-Type', '')
        print("  -> Content-Type:", content_type)
        content = response.content.decode('utf-8')[:300]
        print("  -> Preview CSV:", content.replace("\n", " | "))
        self.assertIn('text/csv', content_type)
        self.assertIn("Оцените по шкале 1-5", content)

    # ==============================================================
    # 🔹 3. Экспорт XLSX
    # ==============================================================
    def test_export_xlsx(self):
        print("\n[Test] POST /api/analytics/{survey_id}/export/ (XLSX)")
        url = reverse('export-data', args=[self.survey.pk])
        payload = {"format": "xlsx"}
        response = self.client.post(url, data=payload)
        print("  -> Status:", response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content_type = response.get('Content-Type', '')
        print("  -> Content-Type:", content_type)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            content_type
        )
        print("  -> Длина файла (байт):", len(response.content))

    # ==============================================================
    # 🔹 4. Общий Dashboard
    # ==============================================================
    def test_dashboard_data(self):
        print("\n[Test] GET /api/analytics/{survey_id}/dashboard/")
        url = reverse('dashboard-data', args=[self.survey.pk])
        response = self.client.get(url)
        print("  -> Status:", response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        print("  -> Ключи в ответе:", list(data.keys()))
        self.assertIn('dashboard', data)

        dashboard = data['dashboard']
        print("  -> Содержимое dashboard:", json.dumps(dashboard, ensure_ascii=False, indent=2))
        self.assertIsInstance(dashboard, dict)

    # ==============================================================
    # 🔹 5. Respondent Dashboard (агрегация характеристик)
    # ==============================================================
    def test_respondent_dashboard(self):
        print("\n[Test] GET /api/analytics/{survey_id}/respondent-dashboard/")
        url = reverse('respondent-dashboard', args=[self.survey.pk])
        response = self.client.get(url)
        print("  -> Status:", response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        print("  -> Ключи ответа:", list(data.keys()))
        self.assertIn('characteristics_summary', data, "Нет ключа 'characteristics_summary'")

        summary = data['characteristics_summary']
        print("  -> Найденные характеристики:", list(summary.keys()))
        self.assertIn("Пол", summary)
        self.assertIn("Возраст", summary)

        gender_data = summary["Пол"]
        print("  -> Детали по 'Пол':", json.dumps(gender_data, ensure_ascii=False, indent=2))
        self.assertIn("distribution", gender_data)
        self.assertEqual(gender_data["type"], "choice")

        dist = gender_data["distribution"]
        self.assertIsInstance(dist, list)
        self.assertGreater(len(dist), 0)
        found = any(d["value"] == "Мужской" and d["percent"] == 100.0 for d in dist)
        self.assertTrue(found, f"Не найден ожидаемый элемент 'Мужской' в {dist}")

        age_data = summary["Возраст"]
        print("  -> Детали по 'Возраст':", json.dumps(age_data, ensure_ascii=False, indent=2))
        self.assertIn("distribution", age_data)
        dist2 = age_data["distribution"]
        found2 = any(d["value"] == "30" and d["percent"] == 100.0 for d in dist2)
        self.assertTrue(found2, f"Не найден возраст 30 в {dist2}")
