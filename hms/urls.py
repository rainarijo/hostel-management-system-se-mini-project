from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),     # developer tool, not the Administrator UI
    path("accounts/", include("apps.accounts.urls")),
    path("students/", include("apps.students.urls")),
    path("rooms/", include("apps.rooms.urls")),
    path("", include("apps.allocation.urls")),          # /allocation/, /applications/, /manage/windows/
    path("complaints/", include("apps.complaints.urls")),
    path("fees/", include("apps.fees.urls")),
    path("reports/", include("apps.reports.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("", include("apps.core.urls")),
]
