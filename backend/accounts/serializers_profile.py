from rest_framework import serializers
from .models import Users

class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ['user_id', 'name', 'email', 'role']

class UserStatsSerializer(serializers.Serializer):
    completed_surveys = serializers.IntegerField()
    earned_money = serializers.DecimalField(max_digits=10, decimal_places=2)
