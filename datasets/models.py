# -*- coding: utf-8 -*-
from django.db import models
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
import os
from django.conf import settings


# def upload_to(instance, filename):
#     allowed_extensions = {'.raw', '.baf', '.yep', '.mgf', '.mzml', '.mzxml', '.fasta'}
#     fext = os.path.splitext(filename)[-1].lower()
#     if fext in allowed_extensions:
#         upfolder = fext[1:]
#     else:
#         upfolder = 'other'
#     return os.path.join('uploads', upfolder, filename)


class BaseDocument(models.Model):
    # filepath = models.FileField(upload_to=upload_to)
    date_added = models.DateTimeField(auto_now_add=True)
    userid = models.ForeignKey(User)

    def name(self):
        return os.path.split(self.docfile.name)[-1]

    def path(self):
        return os.path.join(settings.MEDIA_ROOT, self.docfile.name)

    class Meta:
        abstract = True


def upload_to_basic(folder, filename, userid):
    return os.path.join('uploads', folder, str(userid), filename)


def upload_to_spectra(instance, filename):
    return upload_to_basic('spectra', filename, instance.userid.id)


def upload_to_fasta(instance, filename):
    return upload_to_basic('fasta', filename, instance.userid.id)


def upload_to_raw(instance, filename):
    return upload_to_basic('raw', filename, instance.userid.id)


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
def upload_to_params(instance, filename):
    return upload_to_basic('params', filename, instance.userid.id)
    # return os.path.join('results', str(instance.userid.id), os.path.splitext(filename)[0], filename)


class ParamsFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_params)
    # date_added = models.DateTimeField(auto_now_add=True)
    # resultsid = models.ManyToManyField(SearchRun)
    # userid = models.ForeignKey(User)

class SearchRun(BaseDocument):
    runname = models.CharField(max_length=80, default='test')
    spectra = models.ManyToManyField(SpectraFile)
    fasta = models.ManyToManyField(FastaFile)
    parameters = models.ManyToManyField(ParamsFile)
    # proc = None
    status = models.CharField(max_length=80, default='No info')
    numMSMS = models.BigIntegerField(default=0)
    totalPSMs = models.BigIntegerField(default=0)
    fdr = models.FloatField(default=0.0)
    numPSMs = models.BigIntegerField(default=0)
    numPeptides = models.BigIntegerField(default=0)
    numProteins = models.BigIntegerField(default=0)

    def add_files(self, c):
        self.add_spectra(c['chosenspectra'])
        self.add_fasta(c['chosenfasta'])
        self.add_params(c['chosenparams'])

    def add_spectra(self, spectraobjects):
        for s in spectraobjects:
            self.spectra.add(s)

    def add_fasta(self, fastaobjects):
        for s in fastaobjects:
            self.fasta.add(s)

    def add_params(self, paramsobjects):
        for s in paramsobjects:
            self.parameters.add(s)

    def name(self):
        return os.path.split(self.runname)[-1]

    def add_proc(self, proc):
        self.proc = proc

    def change_status(self, message):
        self.status = message
        self.save()