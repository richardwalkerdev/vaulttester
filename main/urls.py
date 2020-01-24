from django.urls import path

from . import views

urlpatterns = [
    path('kv/', views.kv, name="kv"),
    path('aws/', views.aws, name="aws"),
    path('ec2/', views.ec2, name="ec2"),
]
