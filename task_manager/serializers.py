from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ScheduledTask
from .models import Task

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user


class TaskSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'status', 'created_by', 'created_at']


class ScheduledTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledTask
        fields = [
            'id',
            'title',
            'description',
            'status',
            'scheduled_time',
            'processing_status',
            'failure_reason',
            'created_at'
        ]
        read_only_fields = ['processing_status', 'failure_reason', 'created_at']