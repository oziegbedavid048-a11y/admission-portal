from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Importing this reorders the admin index and drops the screens we do not use.
from config import admin as _gabstep_admin  # noqa: F401

# The admin is the admissions desk, so it is named for the job rather than for
# Django. The index template adds a short orientation note above the app list.
admin.site.site_header = "Gabstep admissions desk"
admin.site.site_title = "Gabstep admin"
admin.site.index_title = "What needs your attention"
admin.site.index_template = "admin/gabstep_index.html"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/applications/", include("apps.applications.urls")),
    path("api/partners/", include("apps.partners.urls")),
    path("api/supervisors/", include("apps.partners.supervisor_urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
