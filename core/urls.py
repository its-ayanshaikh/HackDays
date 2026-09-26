from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.index, name="dashboard_page"),
    path("ask-ai/", views.index, name="ask_page"),
    path("market-focus/", views.index, name="focus_page"),
    path("anomaly-radar/", views.index, name="radar_page"),
    path("data-explorer/", views.index, name="explorer_page"),
    path("history/", views.index, name="history_page"),
    path("settings/", views.index, name="settings_page"),
    path("ask/", views.ask, name="ask"),
    path("health/", views.health, name="health"),
    path("api/dashboard/", views.dashboard, name="dashboard"),
    path("api/tables/", views.tables, name="tables"),
    path("api/table/<str:name>/", views.table_preview, name="table_preview"),
    path("api/nations/", views.nations, name="nations"),
    path("api/focus/<str:nation>/", views.focus, name="focus"),
    path("api/anomaly-radar/", views.anomaly_radar, name="anomaly_radar"),
]
