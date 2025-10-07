from django.urls import path
from .views import (
    SurveyCreateView, MySurveysView, SurveyRetrieveUpdateDeleteView,
    SurveyArchiveView, ArchivedSurveysListView, SurveyRestoreView,
    QuestionCreateView, QuestionUpdateView, SurveyQuestionDeleteView,
    SurveyQuestionLinkView, SurveyQuestionsListView,
    RespondentAnswerView, SurveyAnswersView,
    SurveyToggleStatusView, AvailableSurveysView,
    ExportSurveyQuestionsView, ImportSurveyQuestionsView,
    MySurveyProgressView, SurveyProgressUpdateView,
    RespondentSurveyAnswersView, RespondentAnswerDetailView
)

urlpatterns = [
    # --- Surveys ---
    path('create/', SurveyCreateView.as_view(), name='survey-create'),
    path('my/', MySurveysView.as_view(), name='survey-my'),
    path('<int:survey_id>/', SurveyRetrieveUpdateDeleteView.as_view(), name='survey-get-update-delete'),
    path('<int:survey_id>/status/', SurveyToggleStatusView.as_view(), name='survey-toggle-status'),
    path('<int:survey_id>/archive/', SurveyArchiveView.as_view(), name='survey-archive'),
    path('archived/', ArchivedSurveysListView.as_view(), name='survey-archived-list'),
    path('archived/<int:archive_id>/restore/', SurveyRestoreView.as_view(), name='survey-restore'),
    path('available/', AvailableSurveysView.as_view(), name='survey-available'),
    path('my-progress/', MySurveyProgressView.as_view(), name='my-survey-progress'),
    path('<int:survey_id>/progress/', SurveyProgressUpdateView.as_view(), name='survey-progress-update'),
    path('respondent/<int:survey_id>/answers/', RespondentSurveyAnswersView.as_view(), name='respondent-survey-answers'),


    # --- Questions ---
    path('questions/create/', QuestionCreateView.as_view(), name='question-create'),
    path('questions/<int:question_id>/', QuestionUpdateView.as_view(), name='question-update'),
    path('questions/unlink/<int:question_id>/', SurveyQuestionDeleteView.as_view(), name='survey-question-unlink'),
    path('questions/link/', SurveyQuestionLinkView.as_view(), name='question-link'),
    path('<int:survey_id>/questions/', SurveyQuestionsListView.as_view(), name='survey-questions'),

    # --- Answers ---
    path('answer/', RespondentAnswerView.as_view(), name='respondent-answer'),
    path('<int:survey_id>/answers/', SurveyAnswersView.as_view(), name='survey-answers'),

    path("<int:survey_id>/export/<str:format_type>/", ExportSurveyQuestionsView.as_view(), name="survey-export"),
    path("<int:survey_id>/import/<str:format_type>/", ImportSurveyQuestionsView.as_view(), name="survey-import"),
    # path('questions/<int:question_id>/my-answer/', RespondentAnswerDetailView.as_view(), name='respondent-answer-detail'),
]
