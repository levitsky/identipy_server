from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib import admin

urlpatterns = patterns('',
	(r'^base/', include('server.urls')),
	(r'^$', RedirectView.as_view(url='/base/base/')),
) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

