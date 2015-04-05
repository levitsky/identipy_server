from django.conf.urls import include, url
from django.conf import settings
from django.contrib import admin
from django.views.generic.base import RedirectView

urlpatterns = [
	url(r'^data/', include('datasets.urls', namespace='datasets')),
        url(r'^admin/', include(admin.site.urls)),
        url(r'^$', RedirectView.as_view(url='/data')),
]
