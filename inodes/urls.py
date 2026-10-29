"""Rutas URL para la aplicación de inodos."""

from django.urls import path

from . import views

app_name = "inodes"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/action/", views.action_api, name="action_api"),
]
