from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicationViewSet, DraftView

router = DefaultRouter()
router.register("", ApplicationViewSet, basename="application")

urlpatterns = [
    path("draft/", DraftView.as_view(), name="application-draft"),
    path("", include(router.urls)),
]
