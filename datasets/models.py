# -*- coding: utf-8 -*-
from django.db import models
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
import os


def upload_to(instance, filename):
    allowed_extensions = {'.raw', '.baf', '.yep', '.mgf', '.mzml', '.mzxml', '.fasta'}
    fext = os.path.splitext(filename)[-1].lower()
    if fext in allowed_extensions:
        upfolder = fext[1:]
    else:
        upfolder = 'other'
    return os.path.join('uploads', upfolder, filename)


class Document(models.Model):
    docfile = models.FileField(upload_to=upload_to)
    date_added = models.DateTimeField(auto_now_add=True)
    userid = models.ForeignKey(User)
    # userid = models.BigIntegerField(None)

    def __unicode__(self):
        return unicode(self.docfile.name)

    def format(self):
        return os.path.splitext(self.docfile)[-1][1:]

    def delete(self):
        super(Document, self).delete()
        default_storage.delete(self.docfile.name)

    def name(self):
        return os.path.split(self.docfile.name)[-1]


class SearchRun(models.Model):
    pass


class Parameters(models.Model):
    parfile = models.FileField(upload_to=lambda _, x: 'results/%s/%s.cfg' % (x, x))
    date_added = models.DateTimeField(auto_now_add=True)
    resultsid = models.ForeignKey(SearchRun)
    userid = models.ForeignKey(User)