# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    # url(r'^search_details/([0-9]+)', views.search_details, name='search_details'),
    url(r'^details/([0-9]+)/', views.details, name='details'),
    url(r'^delete/([0-9]+)/', views.delete, name='delete'),
]
