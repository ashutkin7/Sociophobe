from django.urls import path
from .views import (
    SurveyCreateView, MySurveysView, QuestionCreateView, SurveyQuestionLinkView,
    SurveyQuestionsListView, RespondentAnswerView, SurveyAnswersView,
    SurveyToggleStatusView, AvailableSurveysView,
    SurveyRetrieveUpdateDeleteView, SurveyArchiveView, QuestionUpdateView, SurveyQuestionDeleteView
)

urlpatterns = [
    path('create/', SurveyCreateView.as_view(), name='survey-create'),
    path('my/', MySurveysView.as_view(), name='survey-my'),
    path('questions/create/', QuestionCreateView.as_view(), name='question-create'),
    path('questions/link/', SurveyQuestionLinkView.as_view(), name='question-link'),
    path('<int:survey_id>/questions/', SurveyQuestionsListView.as_view(), name='survey-questions'),
    path('answer/', RespondentAnswerView.as_view(), name='respondent-answer'),
    path('<int:survey_id>/answers/', SurveyAnswersView.as_view(), name='survey-answers'),
    path('<int:survey_id>/status/', SurveyToggleStatusView.as_view(), name='survey-toggle-status'),
    path('available/', AvailableSurveysView.as_view(), name='survey-available'),
    path('<int:survey_id>/', SurveyRetrieveUpdateDeleteView.as_view(), name='survey-get-update-delete'),
    path('<int:survey_id>/archive/', SurveyArchiveView.as_view(), name='survey-archive'),
    path('questions/<int:question_id>/', QuestionUpdateView.as_view(), name='question-update'),
    path('questions/unlink/<int:question_id>/',
         SurveyQuestionDeleteView.as_view(), name='survey-question-unlink'),
]
