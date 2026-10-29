from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:report_type>/", views.report_detail, name="detail"),
    path("<slug:report_type>/export/<str:export_format>/", views.export, name="export"),
]
