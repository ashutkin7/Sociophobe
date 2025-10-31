# payments/views.py
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
    WalletSerializer, TransactionSerializer, CalculateCostSerializer, SurveyTopUpSerializer,
    PricingTierSerializer
)
from .models import Wallet, PaymentTransaction, PricingTier, SurveyAccount
from surveys.models import Surveys, RespondentSurveyStatus,SurveyQuestions
from django.contrib.auth import get_user_model
from rest_framework import serializers

from decimal import Decimal, ROUND_HALF_UP
from django.db.models import F


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
            "Выплата инициируется **респондентом** после завершения опроса.\n"
            "Проверки: survey.cost > 0, статус completed, на SurveyAccount достаточно средств, idempotency."
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
                        "survey_account_balance": serializers.DecimalField(max_digits=12, decimal_places=2),
                        "to_balance": serializers.DecimalField(max_digits=12, decimal_places=2),
                    },
                )
            )
        },
        tags=["Платежи"],
    )
    def post(self, request):
        serializer = PayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey_id = serializer.validated_data["survey_id"]
        description = serializer.validated_data.get("description", "")

        respondent = request.user
        survey = get_object_or_404(Surveys, pk=survey_id)

        if getattr(respondent, "role", None) != "respondent":
            return Response({"detail": "Только респонденты могут запрашивать выплаты"},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            rs = RespondentSurveyStatus.objects.get(survey=survey, respondent=respondent)
        except RespondentSurveyStatus.DoesNotExist:
            return Response({"detail": "Респондент не участвовал в этом опросе"}, status=status.HTTP_404_NOT_FOUND)

        if rs.status != "completed":
            return Response({"detail": "Опрос должен быть завершён перед выплатой"}, status=status.HTTP_400_BAD_REQUEST)

        # Определяем сумму выплаты одному респонденту.
        # Возможные случаи:
        # - Если survey.cost сохранён как TOTAL (price_per_survey * max_residents * 1.10),
        #   то вычисляем price_per_survey = survey.cost / (max_residents * 1.10)
        # - Если survey.cost уже хранит цену за одного респондента — используем её.
        if survey.cost is None or survey.cost <= Decimal('0.00'):
            return Response({"detail": "Для опроса не задана корректная сумма (cost)"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Требуем max_residents, чтобы корректно понять структуру cost
        if not survey.max_residents or survey.max_residents <= 0:
            return Response({"detail": "У опроса не задан max_residents"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Предполагаем, что survey.cost == total (price_per_survey * max_residents * 1.10)
            price_per_survey = survey.cost
        except Exception:
            # fallback: если расчёт не прошёл, используем survey.cost как сумму выплаты (на случай несовместимости)
            price_per_survey = Decimal(survey.cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        payout_amount = price_per_survey
        if payout_amount <= Decimal('0.00'):
            return Response({"detail": "Вычисленная сумма выплаты некорректна"}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем, что выплату не делали раньше
        already = PaymentTransaction.objects.filter(
            type="payout",
            related_survey_id=survey_id,
            related_respondent_id=respondent.id,
            status="success",
        ).exists()
        if already:
            return Response({"detail": "Выплата за этот опрос уже была выполнена"}, status=status.HTTP_400_BAD_REQUEST)

        # Берём счёт опроса
        survey_acc, _ = SurveyAccount.objects.get_or_create(survey=survey, defaults={'currency': 'RUB'})

        if survey_acc.balance < payout_amount:
            return Response({'detail': 'На счёте опроса недостаточно средств'}, status=status.HTTP_400_BAD_REQUEST)

        wallet_respondent = get_or_create_wallet(respondent)

        with transaction.atomic():
            tx = PaymentTransaction.objects.create(
                user=respondent,
                type='payout',
                status='pending',
                amount=payout_amount,
                currency=survey_acc.currency,
                description=description or f"Выплата за опрос '{survey.name}'",
                related_survey_id=survey_id,
                related_respondent_id=respondent.id
            )

            # перевод
            survey_acc.withdraw(payout_amount)
            wallet_respondent.deposit(payout_amount)

            tx.mark_success(gateway_data={
                'from_survey_account': survey.survey_id,
                'to_respondent': respondent.email,
                'transferred_at': timezone.now().isoformat()
            })

        return Response({
            "transaction_id": tx.transaction_id,
            "status": tx.status,
            "amount": str(tx.amount),
            "survey_account_balance": str(survey_acc.balance),
            "to_balance": str(wallet_respondent.balance),
        }, status=status.HTTP_200_OK)


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

class CalculateCostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Рассчитать и записать суммарный cost для опроса (survey_id только)",
        description=(
            "Принимает только survey_id. Вычисляет цену одного опроса по тарифам (PricingTier) "
            "по количеству вопросов в опросе, затем умножает на max_residents и добавляет 10% комиссии:\n\n"
            "total = price_per_survey * max_residents * 1.10\n\n"
            "Результат записывается в поле Surveys.cost и возвращается в ответе."
        ),
        request=inline_serializer(
            name="CalculateCostRequest",
            fields={"survey_id": serializers.IntegerField()}
        ),
        responses={200: inline_serializer(name="CalculateCostResponse", fields={
            "survey_id": serializers.IntegerField(),
            "questions_count": serializers.IntegerField(),
            "price_per_survey": serializers.DecimalField(max_digits=10, decimal_places=2),
            "max_residents": serializers.IntegerField(),
            "total_cost": serializers.DecimalField(max_digits=12, decimal_places=2),
        })},
        tags=["Платежи"]
    )
    def post(self, request):
        survey_id = request.data.get("survey_id")
        if not survey_id:
            return Response({"detail": "survey_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        survey = get_object_or_404(Surveys, pk=survey_id)

        # Получаем количество вопросов
        questions_count = SurveyQuestions.objects.filter(survey=survey).count()

        # Находим тариф
        tiers = PricingTier.objects.order_by("min_questions")
        selected = None
        for t in tiers:
            if t.max_questions is None:
                if questions_count >= t.min_questions:
                    selected = t
                    break
            else:
                if t.min_questions <= questions_count <= t.max_questions:
                    selected = t
                    break

        if not selected:
            return Response({"detail": "Не найден тариф для данного количества вопросов"}, status=status.HTTP_404_NOT_FOUND)

        price_per_survey = Decimal(selected.price_per_survey)
        # проверяем max_residents
        if not survey.max_residents or survey.max_residents <= 0:
            return Response({"detail": "У опроса не задано max_residents или он некорректен"}, status=status.HTTP_400_BAD_REQUEST)

        max_residents = int(survey.max_residents)

        # total = price_per_survey * max_residents * 1.10
        total = (price_per_survey * Decimal(max_residents) * Decimal('1.10')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # сохраняем в survey.cost атомарно
        with transaction.atomic():
            survey.cost = price_per_survey
            survey.save(update_fields=['cost', 'updated_at'] if hasattr(survey, 'updated_at') else ['cost'])

        return Response({
            "survey_id": survey.survey_id,
            "questions_count": questions_count,
            "price_per_survey": str(price_per_survey),
            "max_residents": max_residents,
            "total_cost": str(total)
        }, status=status.HTTP_200_OK)


class TopUpSurveyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Пополнение счёта опроса (customer -> survey account)",
        description="Заказчик пополняет баланс конкретного опроса. Это уменьшает риск ошибочных переводов из личного кошелька и позволяет токенизировать и резервировать бюджет опроса.",
        request=SurveyTopUpSerializer,
        responses={200: inline_serializer(name='TopUpSurveyResp', fields={
            'survey_id': serializers.IntegerField(),
            'new_balance': serializers.DecimalField(max_digits=12, decimal_places=2)
        })},
        tags=['Платежи']
    )
    def post(self, request):
        serializer = SurveyTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey = get_object_or_404(Surveys, pk=serializer.validated_data['survey_id'])

        # права: только создатель или модератор
        if request.user != survey.creator and getattr(request.user, 'role', None) != 'moderator':
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        amount = Decimal(serializer.validated_data['amount']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if amount <= Decimal('0.00'):
            return Response({'detail': 'Сумма должна быть больше нуля'}, status=status.HTTP_400_BAD_REQUEST)

        wallet = get_or_create_wallet(request.user)
        if wallet.balance < amount:
            return Response({'detail': 'Недостаточно средств на кошельке заказчика'},
                            status=status.HTTP_400_BAD_REQUEST)

        # комиссия платформы — 10% от общей суммы, чистая сумма для опроса = amount / 1.10
        NET_DIV = Decimal('1.10')
        net_for_survey = (amount / NET_DIV).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        commission = (amount - net_for_survey).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        survey_acc, _ = SurveyAccount.objects.get_or_create(survey=survey, defaults={'currency': wallet.currency})

        with transaction.atomic():
            # списываем со счёта заказчика полную сумму
            wallet.withdraw(amount)
            # пополняем счёт опроса только "чистой" суммой
            survey_acc.deposit(net_for_survey)

            # лог: пополнение счета опроса
            tx_survey = PaymentTransaction.objects.create(
                user=request.user,
                type='topup',
                amount=net_for_survey,
                currency=survey_acc.currency,
                description=f"Пополнение счета опроса {survey.survey_id} (net to survey)",
                related_survey_id=survey.survey_id
            )
            tx_survey.mark_success(gateway_data={'to_survey_account': survey.survey_id})

            # лог: комиссия платформы (можно анализировать отдельно)
            if commission > Decimal('0.00'):
                tx_comm = PaymentTransaction.objects.create(
                    user=request.user,
                    type='commission',
                    amount=commission,
                    currency=survey_acc.currency,
                    description=f"Комиссия платформы за пополнение опроса {survey.survey_id}",
                    related_survey_id=survey.survey_id
                )
                tx_comm.mark_success(gateway_data={'commission': True})

        return Response({'survey_id': survey.survey_id, 'new_balance': str(survey_acc.balance)},
                        status=status.HTTP_200_OK)

class PricingTierListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Список тарифов (PricingTier) — доступно модератору/админу",
        responses={200: PricingTierSerializer(many=True)},
        tags=['Платежи']
    )
    def get(self, request):
        # Только авторизованные пользователи, но список можно показать всем авторизованным;
        # если нужно — ограничить только модераторам, добавьте проверку роли здесь.
        tiers = PricingTier.objects.all().order_by('min_questions')
        return Response(PricingTierSerializer(tiers, many=True).data, status=status.HTTP_200_OK)


class PricingTierDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Получить тариф (только модератор может изменять)",
        request=PricingTierSerializer,
        responses={200: PricingTierSerializer},
        tags=['Платежи']
    )
    def get(self, request, pk: int):
        tier = get_object_or_404(PricingTier, pk=pk)
        return Response(PricingTierSerializer(tier).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="изменить тариф (только модератор может изменять)",
        request=PricingTierSerializer,
        responses={200: PricingTierSerializer},
        tags=['Платежи']
    )
    def post(self, request, pk: int):
        # Только модератор может изменять тарифы
        if getattr(request.user, 'role', None) != 'moderator':
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        tier = get_object_or_404(PricingTier, pk=pk)
        serializer = PricingTierSerializer(tier, data=request.data)
        serializer.is_valid(raise_exception=True)

        # минимально: обновляем и возвращаем
        with transaction.atomic():
            serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="изменить тариф (только модератор может изменять)",
        request=PricingTierSerializer,
        responses={200: PricingTierSerializer},
        tags=['Платежи']
    )
    def patch(self, request, pk: int):
        # поддерживаем частичное обновление (например, только price_per_survey)
        if getattr(request.user, 'role', None) != 'moderator':
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        tier = get_object_or_404(PricingTier, pk=pk)
        serializer = PricingTierSerializer(tier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)