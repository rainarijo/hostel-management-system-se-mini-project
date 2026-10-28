from django.urls import path

from . import views

app_name = "allocation"

# Mounted at the site root by hms/urls.py so /allocation/, /applications/ and /manage/windows/ all live here.
urlpatterns = [
    path("allocation/", views.index, name="index"),
    path("applications/apply/", views.apply, name="apply"),
    path("applications/queue/", views.queue, name="queue"),
    path("applications/auto-allocate/", views.auto_allocate_view, name="auto_allocate"),
    path("applications/<int:pk>/allocate/", views.allocate_view, name="allocate"),
    path("applications/<int:pk>/reject/", views.reject_view, name="reject"),
    path("applications/<str:application_no>/", views.application_detail, name="application_detail"),
    path("room-change-requests/", views.room_change_requests, name="change_requests"),
    path("manage/room-change-requests/", views.room_change_queue, name="change_request_queue"),
    path("manage/room-change-requests/<int:pk>/reject/", views.reject_room_change_request_view,
         name="reject_change_request"),
    path("manage/windows/", views.window_list, name="window_list"),
    path("manage/windows/new/", views.window_create, name="window_create"),
    path("manage/windows/<int:pk>/edit/", views.window_edit, name="window_edit"),
]
