# payments/urls.py
from django.urls import path
from .views import (
    TopUpView, WithdrawView, PayoutView, WalletView, TransactionsListView,
    CalculateCostView, TopUpSurveyView
)

urlpatterns = [
    path('top-up/', TopUpView.as_view(), name='payments-top-up'),
    path('top-up-survey/', TopUpSurveyView.as_view(), name='payments-top-up-survey'),
    path('withdraw/', WithdrawView.as_view(), name='payments-withdraw'),
    path('payout/', PayoutView.as_view(), name='payments-payout'),
    path('calc-cost/', CalculateCostView.as_view(), name='payments-calc-cost'),
    path('wallet/', WalletView.as_view(), name='payments-wallet'),
    path('transactions/', TransactionsListView.as_view(), name='payments-transactions'),
]
