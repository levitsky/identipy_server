from django.conf.urls import url

from . import views
app_name = 'identipy_app'

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^details/([0-9]+)/', views.details, name='details'),
    url(r'^delete/([0-9]+)/', views.delete, name='delete'),
    url(r'^login/', views.loginview, name='loginform'),
    url(r'^auth/', views.auth_and_login, name='auth'),
    url(r'^choose_spectra/', views.files_view_spectra, name='choose'),
    url(r'^logout/', views.logout_view, name='logout'),
    url(r'^contacts/', views.contacts, name='contacts'),
    url(r'^start/', views.searchpage, name='searchpage'),
    url(r'^upload/', views.upload, name='upload'),
    url(r'^status/', views.status, name='getstatus'),
    url(r'^about/', views.about, name='about'),
    url(r'^import/', views.local_import, name='local_import'),
]
