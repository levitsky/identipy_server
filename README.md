IdentiPy Server - a Django-based web interface for IdentiPy
============================================================

Requirements
------------

 - Python 2.7
 - Django
 - django-multiupload
 - identipy and its dependencies
 - MP score and its dependencies

IdentiPy can be found at: https://bitbucket.org/levitsky/identipy
MP score: https://bitbucket.org/markmipt/mp-score

How to run IdentiPy Server
--------------------------

IdentiPy Server currently works on Unix-like operating systems only.
IdentiPy and MP score are important from directories adjacent to IdentiPy
Server. 

Setup
-----

```
$ hg clone https://bitbucket.org/levitsky/identipy_server
$ hg clone https://bitbucket.org/levitsky/identipy
$ hg clone https://bitbucket.org/markmipt/mp-score

$ cd identipy_server
$ python2 manage.py migrate
$ python2 manage.py createuser <username>
```

You can then run Django development server to test your setup:

```
$ python2 manage.py runserver
```

For reliable use, we recommend running IndetiPy Server with a WSGI-compatible
web server application like Apache or Nginx+uWSGI:

https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/