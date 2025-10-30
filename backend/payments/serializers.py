# payments/serializers.py
from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Wallet, PaymentTransaction
User = get_user_model()


class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    currency = serializers.CharField(default='RUB', required=False)
    payment_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Токен/идентификатор платежа от клиента (CloudPayments token / card cryptogram) — нужен для интеграции"
    )
    description = serializers.CharField(required=False, allow_blank=True)
    # Поля для будущей интеграции:
    return_url = serializers.URLField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)

class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    currency = serializers.CharField(default='RUB', required=False)
    destination = serializers.CharField(help_text="Реквизиты вывода (например, реквизиты банковской карты или кошелька)", required=True)
    description = serializers.CharField(required=False, allow_blank=True)

class PayoutSerializer(serializers.Serializer):
    survey_id = serializers.IntegerField()
    respondent_id = serializers.IntegerField()
    # Не передаём сумму: возьмём из Surveys.cost
    description = serializers.CharField(required=False, allow_blank=True)

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['user', 'balance', 'currency']
        read_only_fields = ['user', 'balance', 'currency']

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            'transaction_id', 'created_at', 'user', 'type',
            'status', 'amount', 'currency', 'description',
            'related_survey_id', 'related_respondent_id', 'gateway_data', 'processed_at'
        ]
        read_only_fields = ['transaction_id', 'created_at', 'processed_at', 'status']

class CalculateCostSerializer(serializers.Serializer):
    survey_id = serializers.IntegerField(required=False)
    questions_count = serializers.IntegerField(required=False, min_value=1)

    def validate(self, data):
        if not data.get('survey_id') and not data.get('questions_count'):
            raise serializers.ValidationError("Нужно передать survey_id или questions_count")
        return data

class SurveyTopUpSerializer(serializers.Serializer):
    survey_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    payment_token = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
