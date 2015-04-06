from django.conf.urls import include, url
from django.conf import settings
from django.contrib import admin
from django.views.generic.base import RedirectView

urlpatterns = [
	url(r'^data/', include('datasets.urls', namespace='datasets')),
    url(r'^login/', 'datasets.views.loginview'),
    url(r'^auth/', 'datasets.views.auth_and_login'),
    # url(r'^signup/', 'datasets.views.sign_up_in'),
    url(r'^logout/', 'datasets.views.logout_view'),
        url(r'^admin/', include(admin.site.urls)),
        url(r'^$', RedirectView.as_view(url='/data')),
]
