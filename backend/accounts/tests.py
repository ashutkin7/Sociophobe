from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from captcha.models import CaptchaStore
from accounts.models import Users, Characteristics


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='http://127.0.0.1:3000'
)
class AuthFlowTests(TestCase):
    """🔒 Полный сценарий проверки регистрации, логина, смены и восстановления пароля."""

    def setUp(self):
        self.client = APIClient()
        self.user = Users.objects.create_user(
            email='test@example.com',
            name='Tester',
            role='respondent',
            password='OldPass123'
        )

    def test_01_captcha_generation(self):
        """✅ Генерация капчи"""
        url = reverse('generate-captcha')
        resp = self.client.get(url)
        self.assertEqual(
            resp.status_code, status.HTTP_200_OK,
            f"[Ошибка] Ожидался код 200, получено {resp.status_code}. Ответ: {resp}"
        )
        self.assertIn('captcha_key', resp.data, "[Ошибка] Ключ 'captcha_key' не найден в ответе.")

    def test_02_registration_with_captcha(self):
        """✅ Регистрация с капчей"""
        captcha = CaptchaStore.objects.create(response='abcd')
        url = reverse('register')
        data = {
            'email': 'newuser@example.com',
            'role': 'respondent',
            'password': 'NewPass123',
            'captcha_key': captcha.hashkey,
            'captcha_value': 'abcd'
        }
        resp = self.client.post(url, data, format='json')
        self.assertEqual(
            resp.status_code, status.HTTP_201_CREATED,
            f"[Ошибка] Регистрация не удалась. Код: {resp.status_code}, ответ: {resp}"
        )
        self.assertTrue(
            Users.objects.filter(email='newuser@example.com').exists(),
            "[Ошибка] Пользователь не создан после регистрации."
        )

    def test_03_login_and_change_password(self):
        """✅ Логин и смена пароля"""
        url = reverse('login')
        resp = self.client.post(url, {'email': 'test@example.com', 'password': 'OldPass123'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] Логин не удался: {resp}")
        token = resp.data.get('access')
        self.assertIsNotNone(token, "[Ошибка] Не получен токен авторизации")

        # смена пароля
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('change-password')
        resp = self.client.post(url, {'old_password': 'OldPass123', 'new_password': 'NewPass456'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] Ошибка при смене пароля: {resp}")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456'), "[Ошибка] Пароль не изменился в БД.")

    def test_04_forgot_and_reset_password(self):
        """✅ Забыли пароль и сброс"""
        url = reverse('forgot-password')
        resp = self.client.post(url, {'email': 'test@example.com'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] Ошибка при forgot-password: {resp}")
        self.assertEqual(len(mail.outbox), 1, "[Ошибка] Письмо не было отправлено.")

        token = default_token_generator.make_token(self.user)
        url = reverse('reset-password') + f'?email={self.user.email}'
        resp = self.client.post(url, {'token': token, 'new_password': 'ResetPass789'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] Сброс пароля не удался: {resp}")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ResetPass789'), "[Ошибка] Новый пароль не применился.")


class ProfileTests(TestCase):
    """👤 Проверка профиля и статистики"""

    def setUp(self):
        self.client = APIClient()
        self.user = Users.objects.create_user(
            email='profile@example.com',
            name='ProfileUser',
            role='respondent',
            password='Pass123'
        )
        self.client.force_authenticate(self.user)

    def test_01_get_and_update_profile(self):
        """✅ Получение и обновление профиля"""
        url = reverse('user-me')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] GET /users/me/ → {resp}")
        self.assertEqual(resp.data['email'], self.user.email)

        # update
        data = {'name': 'UpdatedName'}
        resp = self.client.put(url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] PUT /users/me/ → {resp}")
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'UpdatedName')

    def test_02_user_stats(self):
        """✅ Проверка статистики"""
        url = reverse('user-stats')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] /users/me/stats → {resp}")
        self.assertIn('completed_surveys', resp.data)


class CharacteristicsTests(TestCase):
    """🧩 Проверка CRUD характеристик и пользовательского заполнения"""

    def setUp(self):
        self.client = APIClient()
        self.admin = Users.objects.create_superuser(
            email='admin@example.com', name='Admin', role='customer', password='Admin123'
        )
        self.user = Users.objects.create_user(
            email='respondent@example.com', name='User', role='respondent', password='User123'
        )

    def test_01_admin_crud_characteristics(self):
        """✅ Создание, изменение, удаление характеристик (админ)"""
        self.client.force_authenticate(self.admin)

        # CREATE
        url = '/api/admin/characteristics/'
        data = {'name': 'Возраст', 'value_type': 'numeric', 'requirements': '18,99'}
        resp = self.client.post(url, data, format='json')
        self.assertEqual(
            resp.status_code, status.HTTP_201_CREATED,
            f"[Ошибка] Не удалось создать характеристику. Код: {resp.status_code}, ответ: {resp}"
        )
        char_id = resp.data.get('characteristic_id')
        self.assertIsNotNone(char_id, "[Ошибка] characteristic_id отсутствует в ответе")

        # UPDATE
        resp = self.client.put(f'/api/admin/characteristics/{char_id}/', {'requirements': '1,150'}, format='json')
        self.assertEqual(
            resp.status_code, status.HTTP_200_OK,
            f"[Ошибка] Не удалось изменить характеристику. Код: {resp.status_code}, ответ: {resp}"
        )

        # DELETE
        resp = self.client.delete(f'/api/admin/characteristics/{char_id}/')
        self.assertEqual(
            resp.status_code, status.HTTP_204_NO_CONTENT,
            f"[Ошибка] Не удалось удалить характеристику. Код: {resp.status_code}, ответ: {resp}"
        )

    def test_02_user_characteristics_flow(self):
        """✅ Получение и заполнение характеристик пользователем"""
        # Создаём вручную 3 характеристики
        c1 = Characteristics.objects.create(name="Возраст2", value_type="numeric", requirements="18,99")
        c2 = Characteristics.objects.create(name="Пол2", value_type="choice", requirements="м;ж")
        c3 = Characteristics.objects.create(name="Город2", value_type="string", requirements="")

        self.client.force_authenticate(self.user)

        # ALL
        resp = self.client.get('/api/users/characteristics/all/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] GET all → {resp}")

        # VALID UPDATE
        data = [
            {'characteristic_id': c1.characteristic_id, 'value': '25'},
            {'characteristic_id': c2.characteristic_id, 'value': 'м'},
            {'characteristic_id': c3.characteristic_id, 'value': 'Москва'}
        ]
        resp = self.client.post('/api/users/characteristics/update/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"[Ошибка] POST update → {resp}")

        # INVALID NUMERIC
        bad = [{'characteristic_id': c1.characteristic_id, 'value': '150'}]
        resp = self.client.post('/api/users/characteristics/update/', bad, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, f"[Ошибка] Ожидался 400 при неверном диапазоне → {resp}")

        # INVALID CHOICE
        bad = [{'characteristic_id': c2.characteristic_id, 'value': 'другое'}]
        resp = self.client.post('/api/users/characteristics/update/', bad, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, f"[Ошибка] Ожидался 400 при неверном выборе → {resp}")
