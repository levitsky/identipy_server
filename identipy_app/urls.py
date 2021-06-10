from django.urls import path

from . import views
app_name = 'identipy_app'

urlpatterns = [
    path('',                             views.index,              name='index'),
    path('dispatch/',                    views.form_dispatch,      name='form_dispatch'),
    path('delete_search/',               views.delete_search,      name='delete_search'),
    path('summary/<int:pk>/',            views.search_details,     name='details'),
    path('results/<int:pk>/',            views.results_figure,     name='figure'),
    # path('delete/([0-9]+)/',      views.delete,             name='delete'),
    path('login/',                       views.loginview,          name='loginform'),
    path('logout/',                      views.logout_view,        name='logout'),
    path('auth/',                        views.auth_and_login,     name='auth'),
    path('choose/<str:what>/',           views.files_view,         name='choose'),
    path('logout/',                      views.logout_view,        name='logout'),
    path('contacts/',                    views.contacts,           name='contacts'),
    path('start/',                       views.searchpage,         name='searchpage'),
    path('upload/',                      views.upload,             name='upload'),
    path('status/<name_filter>/',        views.status,             name='getstatus'),
    path('status/',                      views.status,             name='getstatus'),
    path('about/',                       views.about,              name='about'),
    path('import/',                      views.local_import,       name='local_import'),
    path('fetch/',                       views.url_import,         name='url_import'),
    path('run/',                         views.runidentipy,        name='run'),
    path('new_mod/',                     views.add_modification,   name='new_mod'),
    path('new_protease/',                views.add_protease,       name='new_protease'),
    path('download/',                    views.getfiles,           name='download'),
    path('show/',                        views.show,               name='show'),
    path('save/',                        views.save_parameters,    name='save'),
    path('email/',                       views.email,              name='email'),
    path('params/<int:searchgroupid>/',  views.showparams,         name='showparams'),
    path('spectrum/',                    views.spectrum,           name='spectrum'),
    path('groupstatus/<int:sgid>/',      views.group_status,       name='groupstatus'),
    path('rename/<int:pk>/',             views.rename,             name='rename'),
    path('repeat/<int:sgid>/',           views.repeat_search,      name='repeat'),
]
