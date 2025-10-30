# payments/tests.py
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model

from surveys.models import Surveys, RespondentSurveyStatus, Questions, SurveyQuestions
from payments.models import Wallet, PaymentTransaction, Payment, SurveyAccount, PricingTier

User = get_user_model()


class PaymentsFullTestCase(APITestCase):
    """
    Полный набор тестов для payments:
    - Wallet (deposit, withdraw)
    - Calculate cost (survey)
    - Пополнение счёта опроса (customer -> survey account)
    - Payout (respondent-initiated)
    - Top-up (user wallet)
    - Withdraw
    - Transactions list / Wallet view
    """

    def setUp(self):
        # пользователи
        self.customer = User.objects.create_user(
            email="customer@test.com", password="12345", role="customer", name="Customer"
        )
        self.respondent = User.objects.create_user(
            email="respondent@test.com", password="12345", role="respondent", name="Respondent"
        )

        # кошельки
        self.customer_wallet = Wallet.objects.create(user=self.customer, balance=Decimal("1000.00"))
        self.respondent_wallet = Wallet.objects.create(user=self.respondent, balance=Decimal("10.00"))

        # тарифы (гарантируем наличие записей)
        PricingTier.objects.get_or_create(min_questions=1, max_questions=20,
                                          defaults={'price_per_survey': Decimal('30.00')})
        PricingTier.objects.get_or_create(min_questions=21, max_questions=100,
                                          defaults={'price_per_survey': Decimal('50.00')})
        # для "более 100" предполагаем max_questions=None
        PricingTier.objects.get_or_create(min_questions=101, max_questions=None,
                                          defaults={'price_per_survey': Decimal('100.00')})

        # опрос — с max_residents (важно для CalculateCostView)
        self.survey = Surveys.objects.create(
            name="Test Survey",
            creator=self.customer,
            cost=None,
            status="active",
            max_residents=10
        )

        # создаём реальные вопросы и привязки (чтобы избежать IntegrityError)
        self.questions = []
        for i in range(1, 6):  # 5 вопросов -> тариф 1..20 => 30 руб за опрос
            q = Questions.objects.create(text_question=f"Q{i}", type_question='text', extra_data={})
            self.questions.append(q)
            SurveyQuestions.objects.create(survey=self.survey, question=q, order=i)

        # респондент завершил опрос
        self.status_completed = RespondentSurveyStatus.objects.create(
            respondent=self.respondent,
            survey=self.survey,
            status="completed",
        )

        self.client = APIClient()

    # -------------------------
    # Calculate cost endpoint
    # -------------------------
    def test_calculate_cost_sets_survey_cost(self):
        """POST /api/payments/calc-cost/ — рассчитывает и сохраняет survey.cost"""
        url = reverse('payments-calc-cost')
        self.client.force_authenticate(user=self.customer)
        resp = self.client.post(url, {"survey_id": self.survey.survey_id}, format="json")
        self.assertEqual(resp.status_code, 200, msg=f"Expected 200 got {resp.status_code}: {resp.data}")

        # пересчитываем ожидаемую сумму:
        # price_per_survey = 30 (для 5 вопросов)
        # total = price_per_survey * max_residents * 1.10 (комиссия 10%)
        expected = (Decimal('30.00') * Decimal(self.survey.max_residents)) * Decimal('1.10')
        self.survey.refresh_from_db()

        # API должен вернуть total_cost и записать его в survey.cost
        self.assertIn('total_cost', resp.data)
        self.assertEqual(Decimal(resp.data['total_cost']), expected.quantize(Decimal('0.01')))
        self.assertEqual(self.survey.cost.quantize(Decimal('0.01')), expected.quantize(Decimal('0.01')))

    # -------------------------
    # Пополнение счёта опроса и Payout (respondent-initiated)
    # -------------------------
    def test_top_up_survey_and_payout_flow(self):
        """Пополнение счета опроса заказчиком и получение выплаты респондентом"""
        # установим cost (может быть рассчитан ранее)
        self.survey.cost = Decimal('50.00')
        self.survey.save()

        url_topup = reverse('payments-top-up-survey')
        self.client.force_authenticate(user=self.customer)

        resp = self.client.post(url_topup, {"survey_id": self.survey.survey_id, "amount": "200.00"}, format="json")
        self.assertEqual(resp.status_code, 200, msg=f"Top-up survey failed: {resp.data}")

        # проверяем создание/пополнение SurveyAccount
        survey_acc = SurveyAccount.objects.get(survey=self.survey)
        survey_acc.refresh_from_db()
        self.customer_wallet.refresh_from_db()

        # баланс survey account должен увеличиться на 200
        self.assertEqual(survey_acc.balance, Decimal('200.00'))
        # баланс кошелька заказчика должен уменьшиться на 200
        self.assertEqual(self.customer_wallet.balance, Decimal('800.00'))

        # теперь респондент запрашивает выплату (успешно)
        url_payout = reverse('payments-payout')
        self.client.force_authenticate(user=self.respondent)

        resp2 = self.client.post(url_payout, {"survey_id": self.survey.survey_id}, format="json")
        self.assertEqual(resp2.status_code, 200, msg=f"Payout failed: {resp2.data}")

        survey_acc.refresh_from_db()
        self.respondent_wallet.refresh_from_db()

        # баланс survey_acc уменьшился на survey.cost
        self.assertEqual(survey_acc.balance, Decimal('150.00'))
        # респондент получил сумму
        self.assertEqual(self.respondent_wallet.balance, Decimal('10.00') + Decimal('50.00'))

        # повторный запрос payout должен вернуть ошибку (double prevention)
        resp3 = self.client.post(url_payout, {"survey_id": self.survey.survey_id}, format="json")
        self.assertEqual(resp3.status_code, 400)
        self.assertIn("Выплата", str(resp3.data))

    def test_top_up_survey_insufficient_wallet(self):
        """Попытка пополнить счет опроса при недостатке средств у заказчика"""
        url_topup = reverse('payments-top-up-survey')
        self.client.force_authenticate(user=self.customer)
        # сперва уменьшим баланс заказчика
        self.customer_wallet.balance = Decimal('10.00')
        self.customer_wallet.save()

        resp = self.client.post(url_topup, {"survey_id": self.survey.survey_id, "amount": "100.00"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Недостаточно", str(resp.data) or "")

    def test_payout_denied_when_survey_account_has_no_funds(self):
        """Payout невозможен если SurveyAccount баланс меньше survey.cost"""
        # убедимся, что счёт пуст
        SurveyAccount.objects.filter(survey=self.survey).delete()

        # задаём cost > 0
        self.survey.cost = Decimal('100.00')
        self.survey.save()

        self.client.force_authenticate(user=self.respondent)
        url_payout = reverse('payments-payout')
        resp = self.client.post(url_payout, {"survey_id": self.survey.survey_id}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("На счёте опроса недостаточно", str(resp.data) or "")

    # -------------------------
    # Wallet top-up / withdraw / view / transactions
    # -------------------------
    def test_top_up_wallet_and_withdraw_and_wallet_view(self):
        """Пополнение кошелька пользователя (top-up), вывод (withdraw) и просмотр баланса (wallet view)"""
        # top-up wallet (user)
        url_topup = reverse('payments-top-up')
        self.client.force_authenticate(user=self.customer)
        resp = self.client.post(url_topup, {"amount": "100.00"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.customer_wallet.refresh_from_db()
        self.assertEqual(self.customer_wallet.balance, Decimal('1100.00'))

        # withdraw
        url_withdraw = reverse('payments-withdraw')
        resp2 = self.client.post(url_withdraw, {"amount": "50.00", "destination": "card_1111"}, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.customer_wallet.refresh_from_db()
        self.assertEqual(self.customer_wallet.balance, Decimal('1050.00'))

        # wallet view
        url_wallet = reverse('payments-wallet')
        resp3 = self.client.get(url_wallet)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn('balance', resp3.data)

    def test_transactions_list_for_customer_and_respondent(self):
        """Проверка списка транзакций:
         - респондент видит только свои транзакции
         - заказчик видит свои транзакции + транзакции, связанные с его опросами
        """
        # создаём транзакции вручную
        # транзакция по customer (topup)
        top_tx = PaymentTransaction.objects.create(user=self.customer, type='topup', amount=Decimal('100.00'),
                                                   currency='RUB', description='topup test')
        # транзакция payout связанная с survey (user=response in record but related_survey_id links to survey)
        payout_tx = PaymentTransaction.objects.create(user=self.respondent, type='payout', amount=Decimal('50.00'),
                                                      currency='RUB', description='payout test',
                                                      related_survey_id=self.survey.survey_id,
                                                      related_respondent_id=self.respondent.id)
        # транзакция withdraw by respondent
        withdraw_tx = PaymentTransaction.objects.create(user=self.respondent, type='withdraw', amount=Decimal('10.00'),
                                                        currency='RUB')

        # проверка для респондента
        self.client.force_authenticate(user=self.respondent)
        url_tr = reverse('payments-transactions')
        resp_r = self.client.get(url_tr)
        self.assertEqual(resp_r.status_code, 200)
        # респондент должен видеть payout_tx и withdraw_tx (и не обязательно top_tx)
        ids = {t['transaction_id'] for t in resp_r.data}
        self.assertIn(withdraw_tx.transaction_id, ids)
        self.assertIn(payout_tx.transaction_id, ids)
        self.assertNotIn(top_tx.transaction_id, ids)

        # проверка для заказчика
        self.client.force_authenticate(user=self.customer)
        resp_c = self.client.get(url_tr)
        self.assertEqual(resp_c.status_code, 200)
        ids_c = {t['transaction_id'] for t in resp_c.data}
        # заказчик должен видеть top_tx (как свой) и payout_tx (т.к. связан с его опросом)
        self.assertIn(top_tx.transaction_id, ids_c)
        self.assertIn(payout_tx.transaction_id, ids_c)

    # -------------------------
    # Модели: базовые проверки / граничные случаи
    # -------------------------
    def test_create_payment_and_marking(self):
        """Создание Payment и пометка succeeded/failed"""
        payment = Payment.objects.create(
            survey=self.survey,
            creator=self.customer,
            respondent=self.respondent,
            amount=Decimal("200.00"),
        )
        payment.mark_succeeded(transaction_id="TXN123")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "succeeded")
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(payment.transaction_id, "TXN123")

        # failed
        payment2 = Payment.objects.create(
            survey=self.survey,
            creator=self.customer,
            respondent=self.respondent,
            amount=Decimal("150.00"),
        )
        payment2.mark_failed("Ошибка шлюза")
        payment2.refresh_from_db()
        self.assertEqual(payment2.status, "failed")
        self.assertIn("Ошибка", payment2.description)

    def test_negative_amount_transaction_raises(self):
        """Попытка создать транзакцию с отрицательной суммой -> ошибка"""
        with self.assertRaises(Exception):
            PaymentTransaction.objects.create(
                user=self.customer,
                type="withdraw",
                amount=Decimal("-100.00")
            )

    def test_currency_field_default_wallet(self):
        """Проверка, что валюта по умолчанию RUB у кошелька"""
        other_user = User.objects.create_user(email="new@test.com", password="123")
        wallet = Wallet.objects.create(user=other_user, balance=Decimal("10.00"))
        self.assertEqual(wallet.currency, "RUB")
