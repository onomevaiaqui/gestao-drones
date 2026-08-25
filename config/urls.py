from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core.auth_views import LoginSistemaView, selecionar_modo_acesso
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        LoginSistemaView.as_view(),
        name="login",
    ),
    path("selecionar-perfil/", selecionar_modo_acesso, name="selecionar_modo_acesso"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
