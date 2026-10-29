"""URLs for processes app."""

from django.urls import path

from . import views

app_name = "processes"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/action/", views.action_api, name="action_api"),
]
