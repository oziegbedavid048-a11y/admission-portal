from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicationViewSet, DraftFileView, DraftView

router = DefaultRouter()
router.register("", ApplicationViewSet, basename="application")

urlpatterns = [
    path("draft/", DraftView.as_view(), name="application-draft"),
    path("draft/files/", DraftFileView.as_view(), name="application-draft-files"),
    path("draft/files/<int:file_id>/", DraftFileView.as_view(), name="application-draft-file"),
    path("", include(router.urls)),
]
