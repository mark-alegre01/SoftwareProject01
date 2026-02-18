from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="core:dashboard", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/", include("core.api_urls")),
    path("core/", include("core.urls")),
]


