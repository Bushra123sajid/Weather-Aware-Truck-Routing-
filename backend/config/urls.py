"""Root URL configuration."""

from django.urls import path

from apps.common.views import HealthView
from apps.geocoding.views import GeocodeView
from apps.heatmap.views import HeatmapView
from apps.planner.views import PlanView

urlpatterns = [
    path("api/health", HealthView.as_view(), name="health"),
    path("api/geocode", GeocodeView.as_view(), name="geocode"),
    path("api/plan", PlanView.as_view(), name="plan"),
    path("api/heatmap", HeatmapView.as_view(), name="heatmap"),
]
