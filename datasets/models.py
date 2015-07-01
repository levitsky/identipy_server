# -*- coding: utf-8 -*-
from django.db import models
from django.core.files.storage import default_storage, FileSystemStorage
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

def upload_to_pepxml(instance, filename):
    return filename


class SpectraFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_spectra)


class FastaFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_fasta)


class RawFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_raw)


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return os.path.join(settings.MEDIA_ROOT, name)#name


class PepXMLFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())


class ResImageFile(BaseDocument):
    docfile = models.ImageField(upload_to=upload_to_pepxml, storage=OverwriteStorage())
    # docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())


class ResCSV(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())
    ftype = models.CharField(max_length=10)


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
    runname = models.CharField(max_length=80)
    spectra = models.ManyToManyField(SpectraFile)
    fasta = models.ManyToManyField(FastaFile)
    parameters = models.ManyToManyField(ParamsFile)
    pepxmlfiles = models.ManyToManyField(PepXMLFile)
    resimagefiles = models.ManyToManyField(ResImageFile)
    csvfiles = models.ManyToManyField(ResCSV)
    # proc = None
    numMSMS = models.BigIntegerField(default=0)
    totalPSMs = models.BigIntegerField(default=0)
    fdr = models.FloatField(default=0.0)
    numPSMs = models.BigIntegerField(default=0)
    numPeptides = models.BigIntegerField(default=0)
    numProteins = models.BigIntegerField(default=0)
    union = models.BooleanField(default=False)

    def add_files(self, c):
        self.add_spectra(c['chosenspectra'])
        self.add_fasta(c['chosenfasta'])
        self.add_params(c['chosenparams'])

    def add_spectra(self, spectraobject):
        # for s in spectraobjects:
        self.spectra.add(spectraobject)
        self.save()

    def add_spectra_files(self, spectrafiles):
        for s in spectrafiles:
            self.spectra.add(s)
            self.save()

    def add_fasta(self, fastaobject):
        # for s in fastaobjects:
        self.fasta.add(fastaobject)
        self.save()

    def add_params(self, paramsobject):
        # for s in paramsobjects:
        self.parameters.add(paramsobject)
        self.save()

    def add_pepxml(self, pepxmlfile):
        self.pepxmlfiles.add(pepxmlfile)
        self.save()

    def add_resimage(self, resimage):
        self.resimagefiles.add(resimage)
        self.save()

    def add_rescsv(self, rescsv):
        self.csvfiles.add(rescsv)
        self.save()

    def get_resimagefiles(self):
        return self.resimagefiles.all()

    def get_pepxmlfiles(self):
        return self.pepxmlfiles.all()

    def get_pepxmlfiles_paths(self):
        return [pep.docfile.name.encode('ASCII') for pep in self.pepxmlfiles.all()]

    def get_spectrafiles_paths(self):
        return [pep.docfile.name.encode('ASCII') for pep in self.spectra.all()]

    def get_fastafile_path(self):
        return [self.fasta.all()[0].docfile.name.encode('ASCII'), ]

    def get_paramfile_path(self):
        return [self.parameters.all()[0].docfile.name.encode('ASCII'), ]

    def get_csvfiles_paths(self, ftype=None):
        # if not os.path.isfile(os.path.dirname(self.csvfiles.filter(ftype='psm')[0].docfile.name.encode('ASCII')) + '/union_PSMs.csv'):
        if ftype:
            return [pep.docfile.name.encode('ASCII') for pep in self.csvfiles.filter(ftype=ftype)]
        else:
            return [pep.docfile.name.encode('ASCII') for pep in self.csvfiles.all()]
        # else:
        #     if ftype:
        #         fname = self.csvfiles.filter(ftype=ftype)[0].docfile.name.encode('ASCII')
        #     else:
        #         fname = self.csvfiles.all()[0].docfile.name.encode('ASCII')
        #     return [os.path.dirname(fname) + '/union_' + os.path.basename(fname).split('_')[-1]]

    def name(self):
        return os.path.split(self.runname)[-1]

    def add_proc(self, proc):
        self.proc = proc
        self.save()

    def calc_results(self):
        from pyteomics import mgf, pepxml
        import csv
        for fn in self.get_spectrafiles_paths():
            self.numMSMS += sum(1 for _ in mgf.read(fn))
        for fn in self.get_pepxmlfiles_paths():
            self.totalPSMs += sum(1 for _ in pepxml.read(fn))
        for fn in self.get_csvfiles_paths(ftype='psm'):
            with open(fn, "r") as cf:
                self.numPSMs += sum(1 for _ in csv.reader(cf)) - 1
        for fn in self.get_csvfiles_paths(ftype='peptide'):
            with open(fn, "r") as cf:
                self.numPeptides += sum(1 for _ in csv.reader(cf)) - 1
        for fn in self.get_csvfiles_paths(ftype='protein'):
            with open(fn, "r") as cf:
                self.numProteins += sum(1 for _ in csv.reader(cf)) - 1
        self.save()

class SearchGroup(BaseDocument):
    groupname = models.CharField(max_length=80, default='test')
    searchruns = models.ManyToManyField(SearchRun)
    fasta = models.ManyToManyField(FastaFile)
    parameters = models.ManyToManyField(ParamsFile)
    status = models.CharField(max_length=80, default='No info')

    def add_files(self, c):
        self.add_fasta(c['chosenfasta'])
        self.add_params(c['chosenparams'])
        self.save()
        for s in c['chosenspectra']:
            newrun = SearchRun(runname=os.path.splitext(s.docfile.name)[0], userid = self.userid)
            newrun.save()
            newrun.add_fasta(self.fasta.all()[0])
            newrun.add_params(self.parameters.all()[0])
            newrun.add_spectra(s)
            newrun.save()
            self.add_searchrun(newrun)
            self.save()
        if len(c['chosenspectra']) > 1:
            newrun = SearchRun(runname='union', userid = self.userid, union=True)
            newrun.save()
            newrun.add_fasta(self.fasta.all()[0])
            newrun.add_params(self.parameters.all()[0])
            newrun.add_spectra_files(c['chosenspectra'])
            newrun.save()
            self.add_searchrun(newrun)
            self.save()

    def add_searchrun(self, searchrunobject):
        self.searchruns.add(searchrunobject)
        self.save()

    def add_fasta(self, fastaobject):
        self.fasta.add(fastaobject[0])
        self.save()

    def add_params(self, paramsobject):
        self.parameters.add(paramsobject[0])
        self.save()

    def get_searchruns(self):
        return self.searchruns.filter(union=False)

    def get_union(self):
        return self.searchruns.filter(union=True)

    def get_searchruns_all(self):
        return self.searchruns.all().order_by('union')

    def name(self):
        return os.path.split(self.groupname)[-1]

    def change_status(self, message):
        self.status = message
        self.save()
