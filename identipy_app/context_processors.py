_menubar = [
            {'id': 'about', 'value': 'about', 'name': 'about'},
            {'id': 'loginform', 'value': 'Log in', 'name': 'loginform'},
            {'id': 'searchpage', 'value': 'Start search', 'name': 'searchpage'},
            {'id': 'upload', 'value': 'Upload files', 'name': 'upload'},
            {'id': 'get_status', 'value': 'Search history', 'name': 'getstatus'},
            {'id': 'contacts', 'value': 'contacts', 'name': 'contacts'}
          ]

_menufields = [{'about', 'loginform', 'contacts'}, {'searchpage', 'upload', 'get_status', 'contacts'}]



def menubar(request):
    fields = _menufields[request.user.is_authenticated()]
    return {'menubar': [item for item in _menubar if item['id'] in fields]}
