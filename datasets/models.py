# -*- coding: utf-8 -*-
from django.db import models
from django.core.files.storage import default_storage, FileSystemStorage
from django.contrib.auth.models import User

from django.conf import settings
import os
os.chdir(settings.BASE_DIR)
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
import sys
sys.path.append('../identipy/')
import csv
from identipy.utils import CustomRawConfigParser


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
    user = models.ForeignKey(User)

    def name(self):
        return os.path.split(self.docfile.name)[-1]

    def path(self):
        return os.path.join(settings.MEDIA_ROOT, self.docfile.name)

    class Meta:
        abstract = True


def upload_to_basic(folder, filename, user):
    return os.path.join('uploads', folder, str(user), filename)


def upload_to_spectra(instance, filename):
    return upload_to_basic('spectra', filename, instance.user.id)


def upload_to_fasta(instance, filename):
    return upload_to_basic('fasta', filename, instance.user.id)


def upload_to_raw(instance, filename):
    return upload_to_basic('raw', filename, instance.user.id)

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
    ftype = models.CharField(max_length=5, default='.png')
    # docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())


class ResCSV(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())
    ftype = models.CharField(max_length=10)


def upload_to_params(instance, filename):
    return upload_to_basic('params', filename, instance.user.id)


class ParamsFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_params)
    type = models.IntegerField(default=3)


class SearchGroup(BaseDocument):
    groupname = models.CharField(max_length=80, default='test')
    # searchruns = models.ManyToManyField(SearchRun)
    fasta = models.ManyToManyField(FastaFile)
    parameters = models.ManyToManyField(ParamsFile)
    status = models.CharField(max_length=80, default='No info')

    def add_files(self, c):
        import django.db
        django.db.connection.close()
        self.add_fasta(c['chosenfasta'])
        self.add_params(sfForms=c['SearchForms'], paramtype=c['paramtype'])
        self.save()
        for s in c['chosenspectra']:
            newrun = SearchRun(searchgroup_parent=self, runname=os.path.splitext(s.docfile.name)[0], user = self.user)
            newrun.save()
            newrun.add_fasta(self.fasta.all()[0])
            newrun.add_params(self.parameters.all()[0])
            newrun.add_spectra(s)
            newrun.save()
            # self.add_searchrun(newrun)
            self.save()
        if len(c['chosenspectra']) > 1:
            newrun = SearchRun(searchgroup_parent=self, runname='union', user = self.user, union=True)
            newrun.save()
            newrun.add_fasta(self.fasta.all()[0])
            newrun.add_params(self.parameters.all()[0])
            newrun.add_spectra_files(c['chosenspectra'])
            newrun.save()
            # self.add_searchrun(newrun)
            self.save()

    # def add_searchrun(self, searchrunobject):
    #     self.searchruns.add(searchrunobject)
    #     self.save()

    def add_fasta(self, fastaobject):
        import django.db
        django.db.connection.close()
        self.fasta.add(fastaobject[0])
        self.save()

    def add_params(self, sfForms, paramtype=3):
        import django.db
        django.db.connection.close()
        from aux import save_params_new
        paramobj = save_params_new(sfForms=sfForms, uid=self.user, paramsname=False, paramtype=paramtype, request=False)
        self.parameters.add(paramobj)
        self.save()

    def get_searchruns(self):
        import django.db
        django.db.connection.close()
        return self.searchrun_set.filter(union=False)
        # return self.searchruns.filter(union=False)

    def get_union(self):
        import django.db
        django.db.connection.close()
        return self.searchrun_set.filter(union=True)
        # return self.searchruns.filter(union=True)

    def get_searchruns_all(self):
        import django.db
        django.db.connection.close()
        return self.searchrun_set.all().order_by('union')
        # return self.searchruns.all().order_by('union')

    def name(self):
        import django.db
        django.db.connection.close()
        return os.path.split(self.groupname)[-1]

    def change_status(self, message):
        import django.db
        django.db.connection.close()
        self.status = message
        self.save()



class SearchRun(BaseDocument):
    searchgroup_parent = models.ForeignKey(SearchGroup)
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
    fdr_psms = models.FloatField(default=0.0)
    fdr_prots = models.FloatField(default=-1.0)
    numPSMs = models.BigIntegerField(default=0)
    numPeptides = models.BigIntegerField(default=0)
    numProteins = models.BigIntegerField(default=0)
    union = models.BooleanField(default=False)

    def set_FDRs(self):
        raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
        raw_config.read(self.parameters.all()[0].path())
        self.fdr_psms = raw_config.getfloat('options', 'FDR')
        self.fdr_prots = raw_config.getfloat('options', 'protFDR')
        self.save()

    def get_prots_FDR(self):
        if self.fdr_prots >= 0:
            return self.fdr_prots
        else:
            return 'no'

    def add_files(self, c):
        import django.db
        django.db.connection.close()
        self.add_spectra(c['chosenspectra'])
        self.add_fasta(c['chosenfasta'])
        self.add_params(sfForms=c['SearchForms'])

    def add_spectra(self, spectraobject):
        import django.db
        django.db.connection.close()
        # for s in spectraobjects:
        self.spectra.add(spectraobject)
        self.save()

    def add_spectra_files(self, spectrafiles):
        import django.db
        django.db.connection.close()
        for s in spectrafiles:
            self.spectra.add(s)
            self.save()

    def add_fasta(self, fastaobject):
        import django.db
        django.db.connection.close()
        # for s in fastaobjects:
        self.fasta.add(fastaobject)
        self.save()

    def add_params(self, paramsobject):
        import django.db
        django.db.connection.close()
        # for s in paramsobjects:
        self.parameters.add(paramsobject)
        self.save()

    def add_pepxml(self, pepxmlfile):
        import django.db
        django.db.connection.close()
        self.pepxmlfiles.add(pepxmlfile)
        self.save()

    def add_resimage(self, resimage):

        import django.db
        django.db.connection.close()
        self.resimagefiles.add(resimage)
        self.save()

    def add_rescsv(self, rescsv):

        import django.db
        django.db.connection.close()
        self.csvfiles.add(rescsv)
        self.save()

    def get_resimagefiles(self, ftype='.png'):
        import django.db
        django.db.connection.close()
        def get_index(val, custom_list):
            for idx, v in enumerate(custom_list):
                if val == v or (v == 'potential modifications' and val.startswith(v)):
                    return idx
        custom_order = ['RT experimental',
                        'precursor mass',
                        'peptide length',
                        'sumi',
                        'nsaf',
                        'empai',
                        'rt difference, min',
                        'precursor mass difference, ppm',
                        'fragment mass tolerance, da',
                        'potential modifications',
                        'isotopes mass difference, da',
                        'missed cleavages, protease 1',
                        'psm count',
                        'psms per protein',
                        'charge states',
                        'scores']
        all_images = [doc for doc in self.resimagefiles.filter(ftype=ftype)]
        all_images.sort(key=lambda val: get_index(val.docfile.name.encode('ASCII').split('_')[-1].replace(ftype, '').lower(), custom_order))
        return all_images

    def get_pepxmlfiles(self):
        import django.db
        django.db.connection.close()
        return self.pepxmlfiles.all()

    def get_pepxmlfiles_paths(self):
        import django.db
        django.db.connection.close()
        return [pep.docfile.name.encode('ASCII') for pep in self.pepxmlfiles.all()]

    def get_spectrafiles_paths(self):
        import django.db
        django.db.connection.close()
        return [pep.docfile.name.encode('ASCII') for pep in self.spectra.all()]

    def get_fastafile_path(self):
        import django.db
        django.db.connection.close()
        return [self.fasta.all()[0].docfile.name.encode('ASCII'), ]

    def get_resimage_paths(self, ftype='.png'):
        import django.db
        django.db.connection.close()
        return [pep.docfile.name.encode('ASCII') for pep in self.get_resimagefiles(ftype=ftype)]

    def get_paramfile_path(self):
        import django.db
        django.db.connection.close()
        return [self.parameters.all()[0].docfile.name.encode('ASCII'), ]

    def get_csvfiles_paths(self, ftype=None):
        import django.db
        django.db.connection.close()
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
        from pyteomics import mgf, pepxml, mzml
        for fn in self.get_spectrafiles_paths():
            if fn.lower().endswith('.mgf'):
                self.numMSMS += sum(1 for _ in mgf.read(fn))
            elif fn.lower().endswith('.mzml'):
                self.numMSMS += sum(1 for _ in mzml.read(fn))
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

    def get_detailed(self, ftype):
        from aux import ResultsDetailed
        rd = ResultsDetailed(ftype=ftype, path_to_csv=self.get_csvfiles_paths(ftype=ftype)[0])
        if ftype == 'protein':
            rd.custom_labels(['dbname', 'PSMs', 'peptides', 'LFQ(SIn)'])
        elif ftype in ['peptide', 'psm']:
            rd.custom_labels(['sequence', 'm/z exp', 'RT exp', 'missed cleavages'])
        return rd

class Protease(models.Model):
    name = models.CharField(max_length=80)
    rule = models.CharField(max_length=300, default='RK')
    order_val = models.IntegerField()
    user = models.ForeignKey(User)

    class Meta:
        unique_together = ('name', 'user',)


class Modification(models.Model):
    name = models.CharField(max_length=80)
    label = models.CharField(max_length=30)
    aminoacid = models.CharField(max_length=1)
    mass = models.FloatField()
    user = models.ForeignKey(User)

    class Meta:
        unique_together = ('name', 'user', 'aminoacid', 'mass', 'label')