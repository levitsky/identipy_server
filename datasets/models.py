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


class BaseDocument(models.Model):
    # filepath = models.FileField(upload_to=upload_to)
    date_added = models.DateTimeField(auto_now_add=True)
    userid = models.ForeignKey(User)

    def name(self):
        return os.path.split(self.docfile.name)[-1]

    class Meta:
        abstract = True


def upload_to_basic(folder, filename):
    return os.path.join('uploads', folder, filename)


def upload_to_spectra(instance, filename):
    return upload_to_basic('spectra', filename)


def upload_to_fasta(instance, filename):
    return upload_to_basic('fasta', filename)


def upload_to_raw(instance, filename):
    return upload_to_basic('raw', filename)


class SpectraFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_spectra)


class FastaFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_fasta)


class RawFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_raw)


# class Document(models.Model):
#     docfile = models.FileField(upload_to=upload_to)
#     date_added = models.DateTimeField(auto_now_add=True)
#     userid = models.ForeignKey(User)
#     fext = models.CharField(max_length=10)
#     # userid = models.BigIntegerField(None)
#
#     def __unicode__(self):
#         return unicode(self.docfile.name)
#
#     def delete(self):
#         super(Document, self).delete()
#         default_storage.delete(self.docfile.name)
#
#     def name(self):
#         return os.path.split(self.docfile.name)[-1]


class SearchRun(models.Model):
    pass


def upload_to_params(instance, filename):
    return os.path.join('results', os.path.splitext(filename)[0], filename)


class Parameters(models.Model):
    parfile = models.FileField(upload_to=upload_to_params)
    date_added = models.DateTimeField(auto_now_add=True)
    resultsid = models.ForeignKey(SearchRun)
    userid = models.ForeignKey(User)