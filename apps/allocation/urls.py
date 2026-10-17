from django.urls import path

from . import views

app_name = "allocation"

# Mounted at the site root by hms/urls.py so both the /allocation/ and /manage/windows/ screens live here.
urlpatterns = [
    path("allocation/", views.index, name="index"),
    path("manage/windows/", views.window_list, name="window_list"),
    path("manage/windows/new/", views.window_create, name="window_create"),
    path("manage/windows/<int:pk>/edit/", views.window_edit, name="window_edit"),
]
