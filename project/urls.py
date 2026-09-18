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
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.custom_auth.infrastructure.api.v1.views.retired_legacy_identity_views import (
    RetiredLegacyIdentityRouteView,
)
from project.health import health_check

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
