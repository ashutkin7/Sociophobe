from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Surveys, Questions, SurveyQuestions, RespondentAnswers
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class SurveyFullFlowTest(TestCase):
    """Проверяет полный жизненный цикл опроса с CRUD, архивацией и вопросами."""
    def setUp(self):
        self.client = APIClient()

        # создаём пользователей с обязательным email
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
        """Авторизуем тестового клиента под указанным пользователем."""
        self.client.force_authenticate(user=user)

    def test_full_survey_lifecycle(self):
        self.auth(self.customer)

        # 1. Создание опроса
        create_url = reverse('survey-create')
        resp = self.client.post(create_url, {
            "name": "Тестовый опрос",
            "date_finished": (timezone.now() + timedelta(days=5)).isoformat(),
            "max_residents": 10
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        survey_id = resp.data['survey_id']

        # 2. Обновление опроса
        update_url = reverse('survey-update-delete', args=[survey_id])
        resp = self.client.put(update_url, {"name": "Опрос обновлён"}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], "Опрос обновлён")

        # 3. Создание вопроса
        q_url = reverse('question-create')
        resp = self.client.post(q_url, {"text_question": "Как дела?", "type_question": "text"}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        question_id = resp.data['question_id']

        # 4. Привязка вопроса
        link_url = reverse('question-link')
        resp = self.client.post(link_url, {"survey": survey_id, "question": question_id, "order": 1}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        survey_question_id = resp.data['survey_question_id']

        # 5. Редактирование вопроса
        q_update_url = reverse('question-update', args=[question_id])
        resp = self.client.put(q_update_url, {"text_question": "Как ваше настроение?"}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['text_question'], "Как ваше настроение?")

        # 6. Перевод опроса в active
        status_url = reverse('survey-toggle-status', args=[survey_id])
        resp = self.client.post(status_url, {"status": "active"}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 7. Ответ респондента
        self.auth(self.respondent)
        answer_url = reverse('respondent-answer')
        sq = SurveyQuestions.objects.get(pk=survey_question_id)
        resp = self.client.post(answer_url, {"survey_question": sq.pk, "text_answer": "Хорошо"}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RespondentAnswers.objects.filter(survey_question=sq).exists())

        # 8. Архивация опроса
        self.auth(self.customer)
        archive_url = reverse('survey-archive', args=[survey_id])
        resp = self.client.post(archive_url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'stopped')

        # 9. Отсоединение вопроса
        unlink_url = reverse('survey-question-unlink', args=[survey_question_id])
        resp = self.client.delete(unlink_url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SurveyQuestions.objects.filter(pk=survey_question_id).exists())

        # 10. Удаление опроса
        delete_url = reverse('survey-update-delete', args=[survey_id])
        resp = self.client.delete(delete_url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Surveys.objects.filter(pk=survey_id).exists())
