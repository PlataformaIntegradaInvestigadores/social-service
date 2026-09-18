from django.urls import include, path

app_name = "feeds"

urlpatterns = [
    path("api/v1/", include("apps.feeds.infrastructure.api.v1.urls")),
]
