from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("pharmacy.urls")),
    path("", RedirectView.as_view(pattern_name="pos", permanent=False)),
]
