from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve


def media(request, path):
    """Serve uploads também com DEBUG desligado (instalação local)."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("studies.urls")),
    re_path(r"^media/(?P<path>.*)$", media, name="media"),
]
