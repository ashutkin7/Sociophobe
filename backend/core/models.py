from django.db import models

from surveys.models import Surveys, Questions


class Dashboards(models.Model):
    dashboard_id = models.AutoField(primary_key=True)
    survey = models.OneToOneField(Surveys, on_delete=models.CASCADE)
    row_n = models.IntegerField()
    column_n = models.IntegerField()

    class Meta:
        db_table = 'dashboards'


class Analytics(models.Model):
    analytics_id = models.AutoField(primary_key=True)
    survey = models.ForeignKey(Surveys, on_delete=models.CASCADE)
    question = models.ForeignKey(Questions, on_delete=models.CASCADE)
    diagram_id = models.IntegerField(null=True, blank=True)
    type_diagram = models.CharField(max_length=255, null=True, blank=True)
    data_diagram = models.TextField(null=True, blank=True)

    class Meta:
        
        db_table = 'analytics'
