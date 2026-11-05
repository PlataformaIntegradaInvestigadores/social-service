"""
URL configuration for project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.custom_auth.infrastructure.api.v1.views.retired_legacy_identity_views import (
    RetiredLegacyIdentityRouteView,
)
from project.health import health_check

RASTER_IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")


def media_serve(request, path):
    """Serve uploaded media safely: uploads are untrusted and share the origin
    of the app, so anything that is not a raster image is forced to download
    and no response may be sniffed or run scripts."""
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    if not response.get("Content-Type", "").startswith(RASTER_IMAGE_TYPES):
        response["Content-Disposition"] = "attachment"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'"
    response["X-Content-Type-Options"] = "nosniff"
    return response


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/v1/", include("apps.concensus.infrastructure.api.v1.urls.root_url")),
    path("api/", include("apps.custom_auth.infrastructure.api.v1.urls.root_url")),
    path(
        "internal/profile-sync/",
        include("apps.custom_auth.infrastructure.api.v1.urls.profile_sync_url"),
    ),
    path("api/v1/", include("apps.jobs.infrastructure.api.v1.urls.jobs_urls")),
    path("api/v1/", include("apps.feeds.infrastructure.api.v1.urls")),
    # path('api/', include('apps.concensus.infrastructure.api.v1.urls.debate_url')),
    # Autenticacion legacy de investigadores retirada del monolito.
    re_path(
        r"^auth/.*$",
        RetiredLegacyIdentityRouteView.as_view(),
        {"legacy_route": "auth/magic-link"},
        name="retired-magic-link-auth",
    ),
]

# Company logos and feed post files are public and served by the app itself (the
# gateway proxies /media/ here). Everything else under MEDIA_ROOT, notably
# resumes/ (applicants' CVs), is deliberately NOT routed. This must not depend
# on DEBUG, otherwise turning DEBUG off silently breaks every uploaded image.
urlpatterns += [
    re_path(r"^media/(?P<path>(?:company_logos|feed_posts)/.*)$", media_serve),
]
