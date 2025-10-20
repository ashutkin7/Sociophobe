# payments/urls.py
from django.urls import path
from .views import (
    TopUpView, WithdrawView, PayoutView, WalletView, TransactionsListView
)

urlpatterns = [
    path('top-up/', TopUpView.as_view(), name='payments-top-up'),
    path('withdraw/', WithdrawView.as_view(), name='payments-withdraw'),
    path('payout/', PayoutView.as_view(), name='payments-payout'),
    path('wallet/', WalletView.as_view(), name='payments-wallet'),
    path('transactions/', TransactionsListView.as_view(), name='payments-transactions'),
]
