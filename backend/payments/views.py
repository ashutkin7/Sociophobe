# payments/views.py
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from .serializers import (
    TopUpSerializer, WithdrawSerializer, PayoutSerializer,
    WalletSerializer, TransactionSerializer
)
from .models import Wallet, PaymentTransaction
from surveys.models import Surveys, RespondentSurveyStatus
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


# -----------------------------
# Помощник: получить или создать кошелёк
# -----------------------------
def get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user, defaults={'balance': Decimal('0.00')})
    return wallet


# -----------------------------
# 1) Пополнение баланса (Top-up)
# POST /api/payments/top-up/
# -----------------------------
class TopUpView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Пополнение баланса (customer)",
        description=(
            "Создаёт транзакцию пополнения баланса для пользователя (заказчика).\n\n"
            "Поля, которые рекомендуется передавать для интеграции с CloudPayments:\n"
            "- `payment_token` — токен/криптограмма карты/идентификатор платежа от фронта;\n"
            "- `return_url` — callback/redirect URL после 3DS;\n"
            "- `metadata` — произвольный JSON с данными транзакции.\n\n"
            "Логика: создаём запись PaymentTransaction со статусом `pending`. "
            "После успешного подтверждения платежного провайдера пометить транзакцию `success` и обновить кошелёк."
        ),
        request=TopUpSerializer,
        responses={
            200: inline_serializer(
                name='TopUpResponse',
                fields={
                    'transaction_id': serializers.IntegerField(),
                    'status': serializers.CharField(),
                    'balance': serializers.DecimalField(max_digits=12, decimal_places=2)
                }
            )
        },
        tags=['Платежи']
    )
    def post(self, request):
        # Валидация входных данных
        serializer = TopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        amount = Decimal(data['amount'])
        currency = data.get('currency', 'RUB')
        description = data.get('description', '')

        # Создаём транзакцию в базе
        tx = PaymentTransaction.objects.create(
            user=user,
            type='topup',
            status='pending',
            amount=amount,
            currency=currency,
            description=description,
            gateway_data={'request': {k: v for k, v in data.items() if k in ('payment_token','metadata','return_url')}}
        )

        # NOTE: здесь интеграция с CloudPayments:
        #  - отправляем payment_token на CloudPayments, получаем ответ,
        #  - если success => tx.mark_success(gateway_data=resp), wallet.deposit(...)
        #  - если pending (3ds) => вернуть ссылку/инструкции фронту
        #
        # Для тестовой реализации — принимаем платеж как успешный автоматически:
        try:
            with transaction.atomic():
                wallet = get_or_create_wallet(user)
                wallet.deposit(amount)
                tx.mark_success(gateway_data={'simulated': True, 'received_at': timezone.now().isoformat()})
        except Exception as e:
            tx.mark_failed(gateway_data={'error': str(e)})
            return Response({'detail': 'Ошибка при обработке пополнения', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'transaction_id': tx.transaction_id,
            'status': tx.status,
            'balance': str(wallet.balance)
        }, status=status.HTTP_200_OK)


# -----------------------------
# 2) Запрос на вывод средств (Withdraw)
# POST /api/payments/withdraw/
# -----------------------------
class WithdrawView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Запрос вывода средств",
        description=(
            "Запрос на вывод средств с кошелька (customer или respondent).\n"
            "Поля:\n"
            "- amount: сумма вывода\n"
            "- destination: реквизиты (например, номер карты)\n\n"
            "Логика: если на кошельке достаточно средств — создаём транзакцию withdraw со статусом `pending`.\n"
            "В реальной интеграции: отправлять запрос в платёжный провайдер для исполнения выплаты.\n"
        ),
        request=WithdrawSerializer,
        responses={200: TransactionSerializer},
        tags=['Платежи']
    )
    def post(self, request):
        serializer = WithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        amount = Decimal(data['amount'])
        destination = data['destination']
        description = data.get('description', '')

        wallet = get_or_create_wallet(user)

        # Проверка баланса
        if wallet.balance < amount:
            return Response({'detail': 'Недостаточно средств'}, status=status.HTTP_400_BAD_REQUEST)

        # Создаём транзакцию и переводим в pending (реальное списание — после подтверждения провайдера)
        tx = PaymentTransaction.objects.create(
            user=user,
            type='withdraw',
            status='pending',
            amount=amount,
            currency=wallet.currency,
            description=description,
            gateway_data={'destination': destination}
        )

        # Для простоты — сразу подтверждаем и списываем (в реальном — ждать провайдера)
        try:
            with transaction.atomic():
                wallet.withdraw(amount)
                tx.mark_success(gateway_data={'simulated': True, 'sent_to': destination, 'processed_at': timezone.now().isoformat()})
        except Exception as e:
            tx.mark_failed(gateway_data={'error': str(e)})
            return Response({'detail': 'Ошибка при обработке вывода', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(TransactionSerializer(tx).data, status=status.HTTP_200_OK)


# -----------------------------
# 3) Payout: перевод от заказчика к респонденту после завершения опроса
# POST /api/payments/payout/
# -----------------------------
class PayoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Респондент запрашивает выплату за завершённый опрос",
        description=(
            "Выплата инициируется **респондентом** после завершения опроса.\n\n"
            "Проверки:\n"
            "- Опрос должен иметь положительное поле `cost`\n"
            "- Респондент должен иметь статус `completed`\n"
            "- У заказчика (создателя опроса) должно быть достаточно средств\n"
            "- Выплата по одной паре (survey_id, respondent_id) выполняется только один раз"
        ),
        request=PayoutSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="PayoutResponse",
                    fields={
                        "transaction_id": serializers.IntegerField(),
                        "status": serializers.CharField(),
                        "amount": serializers.DecimalField(max_digits=12, decimal_places=2),
                        "from_balance": serializers.DecimalField(max_digits=12, decimal_places=2),
                        "to_balance": serializers.DecimalField(max_digits=12, decimal_places=2),
                    },
                )
            )
        },
        tags=["Платежи"],
    )
    def post(self, request):
        """💸 Выплата респонденту после завершённого опроса"""
        serializer = PayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey_id = serializer.validated_data["survey_id"]
        description = serializer.validated_data.get("description", "")

        respondent = request.user  # инициатор — респондент

        # Загружаем опрос
        survey = get_object_or_404(Surveys, pk=survey_id)

        # Проверка, что пользователь действительно респондент
        if getattr(respondent, "role", None) != "respondent":
            return Response(
                {"detail": "Только респонденты могут запрашивать выплаты"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Проверка, что опрос завершён респондентом
        try:
            rs = RespondentSurveyStatus.objects.get(survey=survey, respondent=respondent)
        except RespondentSurveyStatus.DoesNotExist:
            return Response(
                {"detail": "Респондент не участвовал в этом опросе"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if rs.status != "completed":
            return Response(
                {"detail": "Опрос должен быть завершён перед выплатой"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверка суммы
        if survey.cost is None or survey.cost <= Decimal("0.00"):
            return Response(
                {"detail": "Для опроса не задана корректная сумма выплаты (cost)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверка на повторную выплату
        already = PaymentTransaction.objects.filter(
            type="payout",
            related_survey_id=survey_id,
            related_respondent_id=respondent.id,
            status="success",
        ).exists()
        if already:
            return Response(
                {"detail": "Выплата за этот опрос уже была выполнена"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, что у заказчика есть деньги
        customer = survey.creator
        wallet_customer = get_or_create_wallet(customer)
        if wallet_customer.balance < survey.cost:
            return Response(
                {"detail": "У заказчика недостаточно средств для выплаты"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Выполняем перевод (атомарно)
        wallet_respondent = get_or_create_wallet(respondent)
        with transaction.atomic():
            # Создаём запись транзакции
            tx = PaymentTransaction.objects.create(
                user=respondent,
                type="payout",
                amount=survey.cost,
                currency=wallet_customer.currency,
                description=description or f"Выплата за опрос '{survey.name}'",
                related_survey_id=survey_id,
                related_respondent_id=respondent.id,
            )

            # Перевод средств
            wallet_customer.withdraw(survey.cost)
            wallet_respondent.deposit(survey.cost)

            tx.mark_success(
                gateway_data={
                    "from_customer": customer.email,
                    "to_respondent": respondent.email,
                    "transferred_at": timezone.now().isoformat(),
                }
            )

        return Response(
            {
                "transaction_id": tx.transaction_id,
                "status": tx.status,
                "amount": str(tx.amount),
                "from_balance": str(wallet_customer.balance),
                "to_balance": str(wallet_respondent.balance),
            },
            status=status.HTTP_200_OK,
        )

# -----------------------------
# 4) Просмотр кошелька и транзакций
# GET /api/payments/wallet/  -> баланс текущего пользователя
# GET /api/payments/transactions/ -> список транзакций текущего пользователя
# -----------------------------
class WalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Просмотр кошелька (баланс) текущего пользователя",
        responses={200: WalletSerializer},
        tags=['Платежи']
    )
    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        return Response({'balance': str(wallet.balance), 'currency': wallet.currency})


class TransactionsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Список транзакций текущего пользователя (для респондента и заказчика)",
        description=(
            "Возвращает список транзакций:\n"
            "- Для респондента: только его собственные операции\n"
            "- Для заказчика: все операции, связанные с его опросами (выплаты респондентам и др.)"
        ),
        responses={200: TransactionSerializer(many=True)},
        tags=['Платежи']
    )
    def get(self, request):
        user = request.user

        # 🔹 Базовый набор — все транзакции текущего пользователя
        qs = PaymentTransaction.objects.filter(user=user)

        # 🔹 Если пользователь — заказчик, добавляем транзакции по его опросам
        if getattr(user, 'role', None) == 'customer':
            from surveys.models import Surveys
            survey_ids = Surveys.objects.filter(creator=user).values_list('survey_id', flat=True)
            if survey_ids:
                qs = PaymentTransaction.objects.filter(
                    Q(user=user) | Q(related_survey_id__in=survey_ids)
                )

        qs = qs.order_by('-created_at')

        return Response(TransactionSerializer(qs, many=True).data)