from surveys.models import Surveys, RespondentSurveyStatus
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('succeeded', 'Успешно'),
        ('failed', 'Ошибка'),
        ('refunded', 'Возврат'),
    ]

    id = models.AutoField(primary_key=True)
    survey = models.ForeignKey(
        Surveys,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Опрос, за который производится выплата"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments_made',
        help_text="Заказчик, который совершает оплату"
    )
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments_received',
        help_text="Респондент, получающий оплату"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Сумма выплаты респонденту"
    )
    currency = models.CharField(max_length=3, default='RUB')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Идентификатор транзакции в CloudPayments"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        verbose_name = "Выплата"
        verbose_name_plural = "Выплаты"

    def save(self, *args, **kwargs):
        # Проверка суммы
        if self.amount <= 0:
            raise ValueError("Сумма должна быть больше нуля")

        # Предотвращаем повторную выплату за тот же опрос
        if Payment.objects.filter(
            survey=self.survey,
            respondent=self.respondent,
            status="succeeded"
        ).exists():
            raise ValueError("Выплата этому респонденту уже произведена")

        super().save(*args, **kwargs)

    def mark_succeeded(self, transaction_id):
        self.status = "succeeded"
        self.paid_at = timezone.now()
        self.transaction_id = transaction_id
        self.save()

    def mark_failed(self, reason):
        self.status = "failed"
        self.description = reason
        self.save()

    def __str__(self):
        return f"{self.survey.name} → {self.respondent.email} ({self.amount} {self.currency}) [{self.status}]"


class Wallet(models.Model):
    """
    Кошелёк пользователя. Одна запись на пользователя.
    Баланс храним Decimal для точности. Валюта — предусмотреть расширение.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='RUB')  # в будущем multi-currency

    class Meta:
        db_table = 'payment_wallet'

    def __str__(self):
        return f"Wallet({self.user.email}): {self.balance} {self.currency}"

    def deposit(self, amount: Decimal):
        with transaction.atomic():
            # reload for safety
            w = Wallet.objects.select_for_update().get(pk=self.pk)
            w.balance = w.balance + Decimal(amount)
            w.save()
            return w

    def withdraw(self, amount: Decimal):
        with transaction.atomic():
            w = Wallet.objects.select_for_update().get(pk=self.pk)
            if w.balance < Decimal(amount):
                raise ValueError("Insufficient funds")
            w.balance = w.balance - Decimal(amount)
            w.save()
            return w


class PaymentTransaction(models.Model):
    TYPE_CHOICES = [
        ('topup', 'Пополнение'),
        ('withdraw', 'Вывод'),
        ('payout', 'Выплата респонденту'),
        ('commission', 'Комиссия платформы'),
        ('refund', 'Возврат'),
    ]

    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
    ]

    transaction_id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_transactions')
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='RUB')
    description = models.TextField(blank=True, null=True)
    related_survey_id = models.IntegerField(null=True, blank=True)
    related_respondent_id = models.IntegerField(null=True, blank=True)
    gateway_data = models.JSONField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payment_transactions'
        indexes = [
            models.Index(fields=['user', 'type']),
            models.Index(fields=['related_survey_id', 'related_respondent_id']),
        ]

    def mark_success(self, gateway_data=None):
        self.status = 'success'
        self.processed_at = timezone.now()
        if gateway_data:
            self.gateway_data = gateway_data
        self.save()

    def mark_failed(self, gateway_data=None):
        self.status = 'failed'
        self.processed_at = timezone.now()
        if gateway_data:
            self.gateway_data = gateway_data
        self.save()

    def save(self, *args, **kwargs):
        # Проверяем положительность суммы
        if self.amount <= 0:
            raise ValueError("Сумма транзакции должна быть положительной")

        # Проверяем дублирование для выплат респондентам
        if self.type == 'payout' and self.related_survey_id and self.related_respondent_id:
            duplicate = PaymentTransaction.objects.filter(
                type='payout',
                related_survey_id=self.related_survey_id,
                related_respondent_id=self.related_respondent_id,
                status='success'
            ).exists()
            if duplicate:
                raise ValueError("Нельзя произвести двойную выплату респонденту за один опрос")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Transaction {self.transaction_id}: {self.type} {self.amount} {self.currency} [{self.status}]"
