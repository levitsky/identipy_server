from django.conf.urls import include, url
from django.conf import settings
from django.contrib import admin

urlpatterns = [
	url(r'^data/', include('datasets.urls')),
        url(r'^admin/', include(admin.site.urls)),
]
