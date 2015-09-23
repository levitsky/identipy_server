# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views
from django.conf import settings

from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


import os
os.chdir(settings.BASE_DIR)

urlpatterns = [
    url(r'^$', views.index, name='index'),
    # url(r'^search_details/([0-9]+)', views.search_details, name='search_details'),
    url(r'^details/([0-9]+)/', views.details, name='details'),
    url(r'^delete/([0-9]+)/', views.delete, name='delete'),
]


urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
