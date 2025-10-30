from surveys.models import Surveys, RespondentSurveyStatus
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.db.models.signals import post_migrate
from django.dispatch import receiver


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

# в payments/models.py (в начало файла импортировать Decimal, models и т.д.)

class PricingTier(models.Model):
    """
    Тариф на оплату за один пройденный опрос в зависимости от количества вопросов.
    min_questions и max_questions включительно.
    Если max_questions is None => диапазон "и больше".
    """
    id = models.AutoField(primary_key=True)
    min_questions = models.PositiveIntegerField()
    max_questions = models.PositiveIntegerField(null=True, blank=True)
    price_per_survey = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'payment_pricing_tier'
        ordering = ['min_questions']

    def clean(self):
        # Проверки на логичность: min <= max (если max задан)
        from django.core.exceptions import ValidationError
        if self.max_questions is not None and self.min_questions > self.max_questions:
            raise ValidationError("min_questions не может быть больше max_questions")

    def save(self, *args, **kwargs):
        # валидация перекрытий
        from django.core.exceptions import ValidationError
        self.clean()

        # собираем все остальные уровни
        qs = PricingTier.objects.all()
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        for other in qs:
            a_min, a_max = self.min_questions, self.max_questions
            b_min, b_max = other.min_questions, other.max_questions
            # приводим None к +inf при сравнении
            a_max_cmp = float('inf') if a_max is None else a_max
            b_max_cmp = float('inf') if b_max is None else b_max
            # Проверяем пересечение интервалов
            if not (a_max_cmp < b_min or b_max_cmp < a_min):
                raise ValidationError(f"Диапазон пересекается с существующим: {other.min_questions}-{other.max_questions or '∞'}")
        super().save(*args, **kwargs)



class SurveyAccount(models.Model):
    id = models.AutoField(primary_key=True)
    survey = models.OneToOneField(Surveys, on_delete=models.CASCADE, related_name='account')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='RUB')

    class Meta:
        db_table = 'survey_account'

    def deposit(self, amount: Decimal):
        from django.db import transaction
        with transaction.atomic():
            sa = SurveyAccount.objects.select_for_update().get(pk=self.pk)
            sa.balance = sa.balance + Decimal(amount)
            sa.save()
            return sa

    def withdraw(self, amount: Decimal):
        from django.db import transaction
        with transaction.atomic():
            sa = SurveyAccount.objects.select_for_update().get(pk=self.pk)
            if sa.balance < Decimal(amount):
                raise ValueError("Insufficient funds in survey account")
            sa.balance = sa.balance - Decimal(amount)
            sa.save()
            return sa

@receiver(post_migrate)
def create_default_pricing(sender, **kwargs):
    if sender.name != 'payments':
        return
    from .models import PricingTier
    defaults = [
        {"min_questions": 1, "max_questions": 20, "price_per_survey": Decimal('30.00')},
        {"min_questions": 21, "max_questions": 100, "price_per_survey": Decimal('50.00')},
        {"min_questions": 101, "max_questions": None, "price_per_survey": Decimal('100.00')},
    ]
    for d in defaults:
        obj, created = PricingTier.objects.get_or_create(
            min_questions=d['min_questions'],
            max_questions=d['max_questions'],
            defaults={"price_per_survey": d['price_per_survey']}
        )
        if created:
            print(f"[INIT] Добавлен тариф: {obj.min_questions} - {obj.max_questions or '∞'} => {obj.price_per_survey}")