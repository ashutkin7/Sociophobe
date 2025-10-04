import csv
import io
import openpyxl
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Surveys, Questions, SurveyQuestions, RespondentAnswers
from django.utils import timezone
from datetime import timedelta
import json
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class SurveyFullFlowTest(TestCase):
    """Проверяет полный жизненный цикл опроса: CRUD, вопросы, ответы, архив, восстановление, импорт/экспорт."""

    def setUp(self):
        self.client = APIClient()

        # пользователи
        self.customer = User.objects.create_user(
            name='customer', email='customer@example.com',
            password='pass', role='customer'
        )
        self.moderator = User.objects.create_user(
            name='moderator', email='moderator@example.com',
            password='pass', role='moderator'
        )
        self.respondent = User.objects.create_user(
            name='respondent', email='respondent@example.com',
            password='pass', role='respondent', is_profile_complete=True
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def log_response(self, step, resp):
        print(f"\n--- {step} ---")
        print("Status code:", resp.status_code)
        try:
            print("Response data:", json.dumps(resp.data, ensure_ascii=False, indent=2))
        except Exception:
            print("Raw content:", resp.content)

    def test_full_survey_lifecycle(self):
        # 1. customer создаёт опрос
        self.auth(self.customer)
        create_url = reverse('survey-create')
        resp = self.client.post(create_url, {
            "name": "Тестовый опрос",
            "date_finished": (timezone.now() + timedelta(days=5)).isoformat(),
            "max_residents": 5,
            "survey_type": "extended"
        }, format='json')
        self.log_response("Создание опроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        survey_id = resp.data['survey_id']

        # 2. Редактирование опроса
        update_url = reverse('survey-get-update-delete', args=[survey_id])
        resp = self.client.put(update_url, {"name": "Опрос обновлён"}, format='json')
        self.log_response("Редактирование опроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['name'], "Опрос обновлён")

        # 3. Создание вопроса
        q_url = reverse('question-create')
        resp = self.client.post(q_url, {
            "text_question": "Как дела?",
            "type_question": "likert",
            "extra_data": {"scale": 5, "min_label": "Плохо", "max_label": "Отлично"}
        }, format='json')
        self.log_response("Создание вопроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        question_id = resp.data['question_id']

        # 4. Привязка вопроса к опросу
        link_url = reverse('question-link')
        resp = self.client.post(link_url, {
            "survey": survey_id, "question": question_id, "order": 1
        }, format='json')
        self.log_response("Привязка вопроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        survey_question_id = resp.data['survey_question_id']

        # 5. Редактирование вопроса
        q_update_url = reverse('question-update', args=[question_id])
        resp = self.client.put(q_update_url, {"text_question": "Как настроение?"}, format='json')
        self.log_response("Редактирование вопроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['text_question'], "Как настроение?")

        # 6. Перевод опроса в active
        status_url = reverse('survey-toggle-status', args=[survey_id])
        resp = self.client.post(status_url, {"status": "active"}, format='json')
        self.log_response("Активация опроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        # 7. respondent отвечает
        self.auth(self.respondent)
        answer_url = reverse('respondent-answer')
        sq = SurveyQuestions.objects.get(pk=survey_question_id)
        resp = self.client.post(answer_url, {
            "survey_question": sq.pk, "text_answer": "5"
        }, format='json')
        self.log_response("Ответ респондента", resp)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(RespondentAnswers.objects.filter(survey_question=sq).exists())

        # 8. Доступные опросы
        available_url = reverse('survey-available')
        resp = self.client.get(available_url)
        self.log_response("Доступные опросы", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(any(s['survey_id'] == survey_id for s in resp.data))

        # 9. Архивация опроса
        self.auth(self.customer)
        archive_url = reverse('survey-archive', args=[survey_id])
        resp = self.client.post(archive_url, {}, format='json')
        self.log_response("Архивация опроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['status'], 'stopped')

        # 10. Проверка списка архивированных
        archived_list_url = reverse('survey-archived-list')
        resp = self.client.get(archived_list_url)
        self.log_response("Список архивированных", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(any(s['survey'] == survey_id for s in resp.data))


        # 11. Восстановление опроса из архива
        archive_id = resp.data[0]['archive_id']
        restore_url = reverse('survey-restore', args=[archive_id])
        resp = self.client.post(restore_url, {}, format='json')
        self.log_response("Восстановление опроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['survey_id'], survey_id)


        # 14. Удаление вопроса
        unlink_url = reverse('survey-question-unlink', args=[question_id])
        resp = self.client.delete(unlink_url)
        self.log_response("Удаление вопроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, resp.data)
        self.assertFalse(Questions.objects.filter(pk=question_id).exists())

        # 15. Удаление опроса
        delete_url = reverse('survey-get-update-delete', args=[survey_id])
        resp = self.client.delete(delete_url)
        self.log_response("Удаление опроса", resp)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, resp.data)
        self.assertFalse(Surveys.objects.filter(pk=survey_id).exists())

    def create_sample_survey(self):
        """Вспомогательная функция: создаёт опрос с 1 вопросом и возвращает survey_id."""
        self.auth(self.customer)
        create_url = reverse('survey-create')
        resp = self.client.post(create_url, {
            "name": "Тестовый опрос",
            "date_finished": (timezone.now() + timedelta(days=5)).isoformat(),
            "max_residents": 5,
            "survey_type": "extended"
        }, format='json')
        survey_id = resp.data['survey_id']

        q_url = reverse('question-create')
        resp = self.client.post(q_url, {
            "text_question": "Как настроение?",
            "type_question": "likert",
            "extra_data": {"scale": 5, "min_label": "Плохо", "max_label": "Отлично"}
        }, format='json')
        question_id = resp.data['question_id']

        link_url = reverse('question-link')
        self.client.post(link_url, {
            "survey": survey_id, "question": question_id, "order": 1
        }, format='json')

        return survey_id

    def test_export_import_csv(self):
        """Проверка экспорта и импорта CSV"""
        survey_id = self.create_sample_survey()

        # --- Экспорт CSV ---
        resp = self.client.get(f"/api/surveys/{survey_id}/export/csv/")
        self.log_response("Экспорт CSV", resp)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        print("\nCSV content:\n", content)
        self.assertIn("Как настроение?", content)

        # --- Импорт CSV ---
        file = SimpleUploadedFile("questions.csv", resp.content, content_type="text/csv")
        resp2 = self.client.post(
            f"/api/surveys/{survey_id}/import/csv/",
            {"file": file},
            format="multipart"
        )
        self.log_response("Импорт CSV", resp2)
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertTrue("created_questions" in resp2.data)


    def test_export_import_xlsx(self):
        """Проверка экспорта и импорта XLSX"""
        survey_id = self.create_sample_survey()

        # --- Экспорт XLSX ---
        resp = self.client.get(f"/api/surveys/{survey_id}/export/xlsx/")
        self.log_response("Экспорт XLSX", resp)
        self.assertEqual(resp.status_code, 200)

        # --- Проверим, что это рабочая книга ---
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        values = [cell.value for cell in ws[2]]
        print("\nXLSX row 2 values:", values)
        self.assertIn("Как настроение?", values)

        # --- Импорт XLSX ---
        file = SimpleUploadedFile(
            "questions.xlsx", resp.content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp2 = self.client.post(
            f"/api/surveys/{survey_id}/import/xlsx/",
            {"file": file},
            format="multipart"
        )
        self.log_response("Импорт XLSX", resp2)
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertTrue("created_questions" in resp2.data)
