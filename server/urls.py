# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('server.views',
    url(r'^base/$', 'base', name='base'),
)