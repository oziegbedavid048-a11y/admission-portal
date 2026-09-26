from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DestinationCountryViewSet,
    FaqViewSet,
    InstitutionViewSet,
    OriginCountryViewSet,
    ProgramViewSet,
    exchange_rates,
    fee_quote,
)

router = DefaultRouter()
router.register("origin-countries", OriginCountryViewSet, basename="origin-country")
router.register("destinations", DestinationCountryViewSet, basename="destination")
router.register("institutions", InstitutionViewSet, basename="institution")
router.register("programs", ProgramViewSet, basename="program")
router.register("faqs", FaqViewSet, basename="faq")

urlpatterns = [
    path("fee-quote/", fee_quote, name="fee-quote"),
    path("exchange-rates/", exchange_rates, name="exchange-rates"),
    path("", include(router.urls)),
]
