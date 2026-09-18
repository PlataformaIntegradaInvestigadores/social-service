from django.urls import path, re_path

from apps.custom_auth.infrastructure.api.v1.views.company_choices_views import (
    CompanyChoicesView,
)
from apps.custom_auth.infrastructure.api.v1.views.company_views import (
    CompanyDetailView,
    CompanyListView,
    CompanyProfileView,
    CompanyUpdateView,
)
from apps.custom_auth.infrastructure.api.v1.views.retired_legacy_identity_views import (
    RetiredLegacyIdentityRouteView,
)

retired_identity_view = RetiredLegacyIdentityRouteView.as_view()


urlpatterns = [
    # Rutas legacy de identidad/perfil/grupos retiradas del monolito.
    # El gateway conserva estos contratos publicos, pero los envia a
    # profile_identity_backend como fuente canonica.
    path(
        "token/",
        retired_identity_view,
        {"legacy_route": "token/"},
        name="retired-token-obtain-pair",
    ),
    path(
        "token/refresh/",
        retired_identity_view,
        {"legacy_route": "token/refresh/"},
        name="retired-token-refresh",
    ),
    path(
        "register/",
        retired_identity_view,
        {"legacy_route": "register/"},
        name="retired-register",
    ),
    re_path(
        r"^users(?:/.*)?$",
        retired_identity_view,
        {"legacy_route": "users"},
        name="retired-users",
    ),
    re_path(
        r"^profile-information(?:/.*)?$",
        retired_identity_view,
        {"legacy_route": "profile-information"},
        name="retired-profile-information",
    ),
    re_path(
        r"^(?:groups|test/user/groups|test/users/groups)(?:/.*)?$",
        retired_identity_view,
        {"legacy_route": "groups"},
        name="retired-groups",
    ),
    # La autenticacion y el alta de cuentas empresariales son canonicas en Identidad.
    path(
        "companies/token/",
        retired_identity_view,
        {"legacy_route": "companies/token/"},
        name="retired-company-token-obtain-pair",
    ),
    path(
        "companies/register/",
        retired_identity_view,
        {"legacy_route": "companies/register/"},
        name="retired-company-register",
    ),
    # El perfil empresarial y Jobs permanecen en el backend social.
    path("companies/", CompanyListView.as_view(), name="company-list"),
    path("companies/profile/", CompanyProfileView.as_view(), name="company-profile"),
    path("companies/choices/", CompanyChoicesView.as_view(), name="company-choices"),
    re_path(
        r"^companies/(?P<pk>[a-zA-Z0-9]+)/$",
        CompanyDetailView.as_view(),
        name="company-detail",
    ),
    re_path(
        r"^companies/(?P<pk>[a-zA-Z0-9]+)/update/$",
        CompanyUpdateView.as_view(),
        name="company-update",
    ),
]
