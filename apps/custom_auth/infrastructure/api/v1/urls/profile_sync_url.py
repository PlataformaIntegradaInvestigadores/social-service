from django.urls import path

from apps.custom_auth.infrastructure.api.v1.views.retired_legacy_identity_views import (
    RetiredLegacyIdentityRouteView,
)
from apps.custom_auth.infrastructure.api.v1.views.company_identity_sync_views import (
    CompanyIdentitySyncView,
)

urlpatterns = [
    path(
        "company-identities/",
        CompanyIdentitySyncView.as_view(),
        name="company-identity-sync",
    ),
    path(
        "users/",
        RetiredLegacyIdentityRouteView.as_view(),
        {"legacy_route": "internal/profile-sync/users"},
        name="profile-sync-users-retired",
    ),
    path(
        "profile-information/",
        RetiredLegacyIdentityRouteView.as_view(),
        {"legacy_route": "internal/profile-sync/profile-information"},
        name="profile-sync-profile-information-retired",
    ),
    path(
        "groups/",
        RetiredLegacyIdentityRouteView.as_view(),
        {"legacy_route": "internal/profile-sync/groups"},
        name="profile-sync-groups-retired",
    ),
    path(
        "group-memberships/",
        RetiredLegacyIdentityRouteView.as_view(),
        {"legacy_route": "internal/profile-sync/group-memberships"},
        name="profile-sync-group-memberships-retired",
    ),
]
