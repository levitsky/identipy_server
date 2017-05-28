from django.conf.urls import url

from . import views
app_name = 'identipy_app'

urlpatterns = [
    url(r'^$',                 views.index,              name='index'),
    url(r'^dispatch/',         views.form_dispatch,      name='form_dispatch'),
    url(r'^delete_search/',    views.delete_search,      name='delete_search'),
    url(r'^summary/([0-9]+)/', views.search_details,     name='details'),
    url(r'^results/([0-9]+)/', views.results_figure,     name='figure'),
    url(r'^delete/([0-9]+)/',  views.delete,             name='delete'),
    url(r'^login/',            views.loginview,          name='loginform'),
    url(r'^logout/',           views.logout_view,        name='logout'),
    url(r'^auth/',             views.auth_and_login,     name='auth'),
    url(r'^choose/(\w*)/',     views.files_view,         name='choose'),
    url(r'^logout/',           views.logout_view,        name='logout'),
    url(r'^contacts/',         views.contacts,           name='contacts'),
    url(r'^start/',            views.searchpage,         name='searchpage'),
    url(r'^upload/',           views.upload,             name='upload'),
    url(r'^status/([^/]*)/',   views.status,             name='getstatus'),
    url(r'^status/',           views.status,             name='getstatus'),
    url(r'^about/',            views.about,              name='about'),
    url(r'^import/',           views.local_import,       name='local_import'),
    url(r'^run/',              views.runidentiprot,      name='run'),
    url(r'^new_mod/',          views.add_modification,   name='new_mod'),
    url(r'^new_protease/',     views.add_protease,       name='new_protease'),
    url(r'^download/',         views.getfiles,           name='download'),
    url(r'^show/',             views.show,               name='show'),
    url(r'^save/',             views.save_parameters,    name='save'),
    url(r'^email/',            views.email,              name='email'),
    url(r'^showparams/',       views.showparams,         name='showparams'),
]
