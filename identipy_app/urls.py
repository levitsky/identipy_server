from django.conf.urls import url

from . import views
app_name = 'identipy_app'

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^details/([0-9]+)/', views.details, name='details'),
    url(r'^delete/([0-9]+)/', views.delete, name='delete'),
    url(r'^login/', views.loginview, name='login'),
    url(r'^auth/', views.auth_and_login, name='auth'),
    url(r'^choose_spectra/', views.files_view_spectra, name='choose'),
    url(r'^logout/', views.logout_view, name='logout'),
]
