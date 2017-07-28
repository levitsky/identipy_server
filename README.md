IdentiPy Server - a Django-based web interface for IdentiPy
============================================================

Requirements
------------

 - Python 2.7
 - Django
 - identipy and its dependencies
    * pyteomics
    * pyteomics.cythonize
    * scipy
 - MP score and its dependencies
    * seaborn
    * mechanize

IdentiPy: https://bitbucket.org/levitsky/identipy

MP score: https://bitbucket.org/markmipt/mp-score

How to run IdentiPy Server
--------------------------

IdentiPy Server currently works on Unix-like operating systems only.
IdentiPy and MP score are imported from directories adjacent to IdentiPy
Server.

Setup
-----

Switch to a directory that will hold the installation, then download the three components of IdentiPy Server, like this:

```
$ hg clone https://bitbucket.org/levitsky/identipy_server
$ hg clone https://bitbucket.org/levitsky/identipy
$ hg clone https://bitbucket.org/markmipt/mp-score
```

Run these commands to initialize the database:

```
$ cd identipy_server
$ python2 manage.py migrate
$ python2 manage.py createsuperuser
$ python2 manage.py createuser <username>
```

You can then run Django development server to test your setup:

```
$ python2 manage.py runserver
```

While the development server is running, you can log into IdentiPy Server and use it in your browser.

Production use
--------------

For more reliable use (especially for multiple-user installations), we recommend running IndetiPy Server with a WSGI-compatible
web server application like Apache or Nginx+uWSGI, instead of the Django development server:

https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/

Example configuration files are included:

 - `uwsgi_parameters` and `identipy.example.ini` - for _uWSGI_;
 - `identipy.example.conf` - for _nginx_;
 - `example-httpd-vhosts.conf` - for _Apache_ with _mod_wsgi_ and virtual hosts.
 
 You may need to edit the following settings in `identipy_server/settings.py`:
 
  - `SECRET_KEY`
  - `DEBUG`
  - `ALLOWED_HOSTS`
  - `STATIC_ROOT`
  - `EMAIL_*` (these are specific to the project)
  
 For explanation of Django settings see the official documentation: https://docs.djangoproject.com/en/1.11/ref/settings/