from rest_framework import serializers
from .models import Users, Surveys

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ['user_id', 'name', 'email', 'role']

class SurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = Surveys
        fields = ['survey_id', 'name', 'creator', 'date_finished', 'max_residents']
