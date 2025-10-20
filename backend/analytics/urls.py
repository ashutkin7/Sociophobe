from django.urls import path
from .views import (
    AnonymizedDataView,
    ExportDataView,
    DashboardDataView,
    RespondentDashboardView,
)

urlpatterns = [
    path('<int:survey_id>/anonymized-data/', AnonymizedDataView.as_view(), name='anonymized-data'),
    path('<int:survey_id>/export/', ExportDataView.as_view(), name='export-data'),
    path('<int:survey_id>/dashboard/', DashboardDataView.as_view(), name='dashboard-data'),
    path('<int:survey_id>/respondent-dashboard/', RespondentDashboardView.as_view(), name='respondent-dashboard'),
]
