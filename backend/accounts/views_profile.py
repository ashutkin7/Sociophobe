from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .serializers_profile import UserMeSerializer, UserStatsSerializer

tag_profile = ['Личный кабинет']


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Получить данные текущего пользователя",
                   responses=UserMeSerializer, tags=tag_profile)
    def get(self, request):
        return Response(UserMeSerializer(request.user).data)

    @extend_schema(summary="Обновить данные профиля",
                   request=UserMeSerializer, responses=UserMeSerializer, tags=tag_profile)
    def put(self, request):
        serializer = UserMeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Статистика респондента",
                   responses=UserStatsSerializer, tags=tag_profile)
    def get(self, request):
        if request.user.role != 'respondent':
            return Response({"detail": "Статистика доступна только респондентам."},
                            status=status.HTTP_403_FORBIDDEN)
        data = {"completed_surveys": 12, "earned_money": "345.50"}
        return Response(UserStatsSerializer(data).data)
