# Identipy Server
# Install Instructions modified from https://bitbucket.org/levitsky/identipy_server/src

FROM python:2.7

# Copy Identipy_server into the container
RUN hg clone https://bitbucket.org/levitsky/identipy_server
RUN hg clone https://bitbucket.org/levitsky/identipy
RUN hg clone https://bitbucket.org/markmipt/mp-score

# Install Identipy Server's Python dependencies
RUN pip install Django==1.11

# Install Identipy's Python dependencies
RUN pip install Pillow numpy pandas psutil scipy
RUN pip install lxml
RUN pip install pyteomics==3.5.1 pyteomics.cythonize==0.2.1 pyteomics.pepxmltk==0.2.7

# Install MP score's dependencies
RUN pip install matplotlib pyparsing python-dateutil functools32 mechanize

# Initialize the database
WORKDIR "/identipy_server"
RUN python manage.py makemigrations
RUN python manage.py migrate

# Create superuser account
RUN python manage.py createsuperuser  --no-input --username admin --email delgrosso@biochem.mpg.de
RUN python manage.py createuser user nomail@gg.de password

## Launch the server!
RUN pip install gunicorn
COPY start.sh /identipy_server/start.sh

EXPOSE 8000
CMD ["bash", "start.sh"]


#CMD ["python", "manage.py", "runserver"]



