IdentiPy Server - a Django-based web interface for IdentiPy
============================================================

Citation
--------

IdentiPy and IdentiPy Server are described in this JPR paper: http://dx.doi.org/10.1021/acs.jproteome.7b00640

Please cite it when using IdentiPy and/or IdentiPy Server or their parts.

License
-------

IdentiPy Server is published under the Apache 2.0 license.


Requirements
------------

 - Python 3
 - Django 2+
 - identipy and its dependencies
    * pyteomics
    * pyteomics.cythonize
    * numpy
    * scipy
    * lxml
      + (if installed with pip, lxml will need development packages of libxml2 and libxslt to compile)
 - Scavager and its dependencies
    * matplotlib
       + cycler, pyparsing, python-dateutil, functools32
    * CatBoost
    * Pandas
    * pyteomics.pepxmltk
 - psutil
 - Pillow

IdentiPy: https://github.com/levitsky/identipy

Scavager: https://github.com/markmipt/scavager

The other dependencies can be installed using `pip` or the package manager of your operating system.

How to run IdentiPy Server
--------------------------

IdentiPy Server currently works on Unix-like operating systems only.
IdentiPy and Scavager need to be properly installed to be imported by IdentiPy Server.

Setup
-----

Download and install IdentiPy and Scavager, either globally or in a virtual environment:

```
$ git clone https://github.com/levitsky/identipy.git
$ cd identipy
$ git checkout exp5  # currently compatible branch

$ pip install . # see identipy exp5 README for extra steps you might need

$ pip install git+https://github.com/markmipt/scavager.git
```

Clone this reposoitory into the location where you want to keep the uploads and results:
```
$ git clone https://github.com/levitsky/identipy_server.git
```

Run these commands to initialize the database:

```
$ cd identipy_server
$ python manage.py makemigrations
$ python manage.py migrate
```

Then create a superuser account to manage the database...

```
$ python manage.py createsuperuser
```
And finally, create a regular user account:

```
$ python manage.py createuser <username>
```

You can then run Django development server to test your setup:

```
$ python manage.py runserver
```

This will start a development server on 127.0.0.1:8000, so it will only be available locally.
If you need to access the server from a local network, specify the IP address and port you need, e.g.:

```
$ python manage.py runserver 192.168.1.2:9000
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

  - Django settings:

    - `SECRET_KEY`
    - `DEBUG`
    - `ALLOWED_HOSTS`
    - `STATIC_ROOT`
    - `DATABASES` (repeat migration after changing this)
    - `CACHES`
    - `LOGGING`

  - Project-specific settings:

    - `EMAIL_*`
    - `NUMBER_OF_PARALLEL_RUNS`
    - `STATUS_UPDATE_INTERVAL`
    - `ZIP_COMPRESSION`
    - `ALLOW_ZIP64`
    - `LOCAL_IMPORT`
    - `URL_IMPORT`


For explanation of Django settings see the official documentation: https://docs.djangoproject.com/en/3.2/ref/settings/
