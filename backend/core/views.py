from rest_framework import viewsets
from .models import Users, Surveys
from .serializers import UserSerializer, SurveySerializer

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Users.objects.all()
    serializer_class = UserSerializer

class SurveyViewSet(viewsets.ModelViewSet):
    queryset = Surveys.objects.all()
    serializer_class = SurveySerializer
