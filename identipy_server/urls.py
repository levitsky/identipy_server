from django.urls import include, path
from django.conf import settings
from django.contrib import admin
from django.views.generic.base import RedirectView

from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    path(r'app/', include('identipy_app.urls')),
    path(r"select2/", include("django_select2.urls")),
    path(r'admin/', admin.site.urls),
    path(r'', RedirectView.as_view(url='app/'))
]


urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

