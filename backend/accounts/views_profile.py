from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_spectacular.utils import extend_schema
from .serializers_profile import (
    UserMeSerializer, UserStatsSerializer,
    CharacteristicSerializer, RespondentCharacteristicSerializer
)
from .models import Characteristics, RespondentCharacteristics

tag_profile = ['Личный кабинет']


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Получить данные текущего пользователя", responses=UserMeSerializer, tags=tag_profile)
    def get(self, request):
        return Response(UserMeSerializer(request.user).data)

    @extend_schema(summary="Обновить данные профиля", request=UserMeSerializer, responses=UserMeSerializer, tags=tag_profile)
    def put(self, request):
        serializer = UserMeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Статистика респондента", responses=UserStatsSerializer, tags=tag_profile)
    def get(self, request):
        if request.user.role != 'respondent':
            return Response({"detail": "Статистика доступна только респондентам."},
                            status=status.HTTP_403_FORBIDDEN)
        data = {"completed_surveys": 12, "earned_money": "345.50"}
        return Response(UserStatsSerializer(data).data)


# ============ ХАРАКТЕРИСТИКИ ПОЛЬЗОВАТЕЛЯ ============

class AllCharacteristicsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Список всех характеристик для заполнения", responses=CharacteristicSerializer(many=True), tags=tag_profile)
    def get(self, request):
        queryset = Characteristics.objects.all()
        return Response(CharacteristicSerializer(queryset, many=True).data)


class UserCharacteristicsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Получить заполненные пользователем характеристики", responses=RespondentCharacteristicSerializer(many=True), tags=tag_profile)
    def get(self, request):
        queryset = RespondentCharacteristics.objects.filter(user=request.user)
        return Response(RespondentCharacteristicSerializer(queryset, many=True).data)


class UpdateUserCharacteristicsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Обновить или добавить характеристики пользователя",
        request=RespondentCharacteristicSerializer(many=True),
        responses=RespondentCharacteristicSerializer(many=True),
        tags=tag_profile
    )
    def post(self, request):
        serializer = RespondentCharacteristicSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        # ✅ Обновляем/добавляем характеристики
        RespondentCharacteristicSerializer.create_or_update(request.user, serializer.validated_data)

        updated = RespondentCharacteristics.objects.filter(user=request.user).select_related(
            'characteristic_value__characteristic'
        )

        print(f"✅ У пользователя ID={request.user.id} теперь {updated.count()} характеристик.")
        return Response(RespondentCharacteristicSerializer(updated, many=True).data, status=200)

# ============ CRUD для Characteristics (админ) ============

class CharacteristicAdminView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Получить все характеристики", responses=CharacteristicSerializer(many=True), tags=['Характеристики'])
    def get(self, request):
        queryset = Characteristics.objects.all()
        return Response(CharacteristicSerializer(queryset, many=True).data)

    @extend_schema(summary="Создать характеристику", request=CharacteristicSerializer, responses=CharacteristicSerializer, tags=['Характеристики'])
    def post(self, request):
        serializer = CharacteristicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CharacteristicDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Изменить характеристику", request=CharacteristicSerializer, responses=CharacteristicSerializer, tags=['Характеристики'])
    def put(self, request, pk):
        characteristic = Characteristics.objects.get(pk=pk)
        serializer = CharacteristicSerializer(characteristic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Удалить характеристику", tags=['Характеристики'])
    def delete(self, request, pk):
        Characteristics.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
