from django.contrib import admin
from django.urls import include, path

from eventos.views import SignupView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/cadastro/", SignupView.as_view(), name="signup"),
    path("contas/", include("django.contrib.auth.urls")),
    path("", include("eventos.urls")),
]
