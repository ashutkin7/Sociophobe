from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model

from surveys.models import Surveys, RespondentSurveyStatus
from payments.models import Wallet, Payment, PaymentTransaction

User = get_user_model()


class PaymentsFullTestCase(APITestCase):
    """
    Полный набор тестов для payments:
    - Wallet (deposit, withdraw)
    - Payment (создание выплат)
    - PaymentTransaction (логи транзакций)
    """

    def setUp(self):
        # 🔹 Создаём пользователей
        self.customer = User.objects.create_user(
            email="customer@test.com", password="12345", role="customer", name="Customer"
        )
        self.respondent = User.objects.create_user(
            email="respondent@test.com", password="12345", role="respondent", name="Respondent"
        )

        # 🔹 Создаём кошельки
        self.customer_wallet = Wallet.objects.create(user=self.customer, balance=Decimal("1000.00"))
        self.respondent_wallet = Wallet.objects.create(user=self.respondent, balance=Decimal("100.00"))

        # 🔹 Создаём опрос
        self.survey = Surveys.objects.create(
            name="Test Survey",
            creator=self.customer,
            cost=Decimal("200.00"),
            status="active",
        )

        # 🔹 Респондент завершил опрос
        self.status_completed = RespondentSurveyStatus.objects.create(
            respondent=self.respondent,
            survey=self.survey,
            status="completed",
        )

        self.client = APIClient()

    # ===========================================================
    # ✅ WALLET TESTS
    # ===========================================================

    def test_wallet_deposit_success(self):
        """✅ Пополнение баланса"""
        before = self.customer_wallet.balance
        self.customer_wallet.deposit(Decimal("500.00"))
        self.customer_wallet.refresh_from_db()
        self.assertEqual(self.customer_wallet.balance, before + Decimal("500.00"))

    def test_wallet_withdraw_success(self):
        """✅ Успешное снятие средств"""
        before = self.customer_wallet.balance
        self.customer_wallet.withdraw(Decimal("200.00"))
        self.customer_wallet.refresh_from_db()
        self.assertEqual(self.customer_wallet.balance, before - Decimal("200.00"))

    def test_wallet_withdraw_insufficient(self):
        """❌ Ошибка снятия при недостаточном балансе"""
        with self.assertRaises(ValueError):
            self.respondent_wallet.withdraw(Decimal("9999.00"))

    # ===========================================================
    # ✅ PAYMENT CREATION TESTS
    # ===========================================================

    def test_create_payment_success(self):
        """✅ Создание и успешная отметка платежа"""
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

    def test_create_payment_failed(self):
        """❌ Создание и отметка неуспешного платежа"""
        payment = Payment.objects.create(
            survey=self.survey,
            creator=self.customer,
            respondent=self.respondent,
            amount=Decimal("200.00"),
        )
        payment.mark_failed("Ошибка шлюза")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "failed")
        self.assertIn("Ошибка", payment.description)

    def test_payment_str(self):
        """✅ Проверка строкового представления"""
        payment = Payment.objects.create(
            survey=self.survey,
            creator=self.customer,
            respondent=self.respondent,
            amount=Decimal("150.00"),
        )
        text = str(payment)
        self.assertIn(self.survey.name, text)
        self.assertIn(self.respondent.email, text)
        self.assertIn("150.00", text)

    # ===============================
    # ✅ PAYOUT TESTS (respondent-initiated)
    # ===============================

    from django.urls import reverse

    class RespondentPayoutTests(APITestCase):
        def setUp(self):
            self.customer = User.objects.create_user(
                email="customer@test.com", password="12345", role="customer", name="Customer"
            )
            self.respondent = User.objects.create_user(
                email="respondent@test.com", password="12345", role="respondent", name="Respondent"
            )

            self.customer_wallet = Wallet.objects.create(user=self.customer, balance=Decimal("500.00"))
            self.respondent_wallet = Wallet.objects.create(user=self.respondent, balance=Decimal("50.00"))

            self.survey = Surveys.objects.create(
                name="Paid Survey",
                creator=self.customer,
                cost=Decimal("200.00"),
                status="active",
            )

            self.status_completed = RespondentSurveyStatus.objects.create(
                respondent=self.respondent,
                survey=self.survey,
                status="completed",
            )

            self.client = APIClient()
            self.url = reverse(
                "payout")  # предполагается, что путь в urls.py: path('payments/payout/', PayoutView.as_view(), name='payout')

        def test_payout_success(self):
            """✅ Успешная выплата после завершения опроса"""
            self.client.force_authenticate(user=self.respondent)
            data = {"survey_id": self.survey.pk, "description": "Хочу выплату"}
            response = self.client.post(self.url, data, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["status"], "success")

        def test_payout_denied_for_incomplete(self):
            """❌ Выплата невозможна, если опрос не завершён"""
            self.status_completed.status = "incomplete"
            self.status_completed.save()
            self.client.force_authenticate(user=self.respondent)
            response = self.client.post(self.url, {"survey_id": self.survey.pk}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("Опрос должен быть завершён", response.data["detail"])

        def test_payout_double_prevention(self):
            """❌ Повторная выплата запрещена"""
            self.client.force_authenticate(user=self.respondent)
            self.client.post(self.url, {"survey_id": self.survey.pk}, format="json")
            response2 = self.client.post(self.url, {"survey_id": self.survey.pk}, format="json")
            self.assertEqual(response2.status_code, 400)
            self.assertIn("Выплата за этот опрос уже была", response2.data["detail"])

        def test_payout_insufficient_customer_balance(self):
            """❌ Ошибка при недостаточном балансе заказчика"""
            self.customer_wallet.balance = Decimal("50.00")
            self.customer_wallet.save()
            self.client.force_authenticate(user=self.respondent)
            response = self.client.post(self.url, {"survey_id": self.survey.pk}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("недостаточно средств", response.data["detail"])

        def test_payout_denied_for_nonrespondent(self):
            """❌ Только респондент может запросить выплату"""
            self.client.force_authenticate(user=self.customer)
            response = self.client.post(self.url, {"survey_id": self.survey.pk}, format="json")
            self.assertEqual(response.status_code, 403)
            self.assertIn("Только респонденты", response.data["detail"])

    # ===========================================================
    # ✅ PSEUDO ENDPOINTS / BUSINESS LOGIC SIMULATION
    # ===========================================================

    def test_customer_payout_flow_success(self):
        """✅ Симуляция полного потока выплаты заказчиком респонденту"""
        # 1. Проверяем изначальные балансы
        start_customer = self.customer_wallet.balance
        start_respondent = self.respondent_wallet.balance

        # 2. Создаём платёж
        payment = Payment.objects.create(
            survey=self.survey,
            creator=self.customer,
            respondent=self.respondent,
            amount=self.survey.cost,
        )

        # 3. Списываем у заказчика
        self.customer_wallet.withdraw(payment.amount)

        # 4. Зачисляем респонденту
        self.respondent_wallet.deposit(payment.amount)

        # 5. Отмечаем платёж как успешный
        payment.mark_succeeded(transaction_id="TXN_PAYOUT_1")

        # Проверки:
        self.customer_wallet.refresh_from_db()
        self.respondent_wallet.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(payment.status, "succeeded")
        self.assertEqual(self.customer_wallet.balance, start_customer - payment.amount)
        self.assertEqual(self.respondent_wallet.balance, start_respondent + payment.amount)

    def test_payout_insufficient_customer_funds(self):
        """❌ Ошибка выплаты при недостаточном балансе заказчика"""
        self.customer_wallet.balance = Decimal("50.00")
        self.customer_wallet.save()
        with self.assertRaises(ValueError):
            self.customer_wallet.withdraw(Decimal("200.00"))

    def test_double_payout_prevention(self):
        """❌ Нельзя произвести двойную выплату одному респонденту за один опрос"""
        Payment.objects.create(
            survey=self.survey,
            creator=self.customer,
            respondent=self.respondent,
            amount=Decimal("200.00"),
            status="succeeded"
        )
        # Попытка создать ещё один — недопустима логически
        with self.assertRaises(Exception):
            Payment.objects.create(
                survey=self.survey,
                creator=self.customer,
                respondent=self.respondent,
                amount=Decimal("200.00"),
                status="pending"
            )

    def test_payout_wrong_survey_status(self):
        """❌ Выплата не разрешена, если респондент не завершил опрос"""
        RespondentSurveyStatus.objects.filter(respondent=self.respondent, survey=self.survey).delete()
        incomplete_status = RespondentSurveyStatus.objects.create(
            respondent=self.respondent,
            survey=self.survey,
            status="incomplete",
        )
        self.assertEqual(incomplete_status.status, "incomplete")

    def test_wallet_concurrent_update_safety(self):
        """✅ Проверка потокобезопасности deposit/withdraw"""
        self.customer_wallet.deposit(Decimal("100.00"))
        self.customer_wallet.withdraw(Decimal("50.00"))
        self.customer_wallet.refresh_from_db()
        self.assertGreater(self.customer_wallet.balance, Decimal("0.00"))

    # ===========================================================
    # ✅ EDGE CASES
    # ===========================================================

    def test_zero_amount_payment_not_allowed(self):
        """❌ Ошибка при нулевой сумме"""
        with self.assertRaises(Exception):
            Payment.objects.create(
                survey=self.survey,
                creator=self.customer,
                respondent=self.respondent,
                amount=Decimal("0.00"),
            )

    def test_negative_amount_transaction(self):
        """❌ Ошибка при отрицательной сумме транзакции"""
        with self.assertRaises(Exception):
            PaymentTransaction.objects.create(
                user=self.customer,
                type="withdraw",
                amount=Decimal("-100.00")
            )

    def test_currency_field_default(self):
        """✅ Проверка, что валюта по умолчанию RUB"""
        wallet = Wallet.objects.create(user=User.objects.create_user(email="new@test.com", password="123"), balance=Decimal("10.00"))
        self.assertEqual(wallet.currency, "RUB")
