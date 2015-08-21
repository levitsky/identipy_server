# -*- coding: utf-8 -*-
from django.db import models
from django.core.files.storage import default_storage, FileSystemStorage
from django.contrib.auth.models import User
import os
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
import sys
sys.path.append('../identipy/')
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
        self.add_fasta(c['chosenfasta'])
        self.add_params(c['SearchParametersForm'], c['paramtype'])
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
        self.fasta.add(fastaobject[0])
        self.save()

    def add_params(self, SearchParametersForm_values, paramtype=3):
        # for s in paramsobjects:
        SearchParametersForm_values = {v.name: v.value() for v in SearchParametersForm_values}
        paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), user=self.user, type=paramtype)
        raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
        raw_config.read(paramobj.docfile.name.encode('ASCII'))
        for section in raw_config.sections():
            for param in raw_config.items(section):
                if param[0] in SearchParametersForm_values:
                    orig_choices = raw_config.get_choices(section, param[0])
                    if orig_choices == 'type>boolean':
                        tempval = ('1' if SearchParametersForm_values[param[0]] else '0')
                    else:
                        tempval = SearchParametersForm_values[param[0]]
                    raw_config.set(section, param[0], tempval + '|' + orig_choices)
        if raw_config.getboolean('options', 'use auto optimization'):
            raw_config.set('misc', 'first stage', 'identipy.extras.optimization')
        else:
            raw_config.set('misc', 'first stage', '')
        raw_config.set('output', 'precursor accuracy unit', raw_config.get('search', 'precursor accuracy unit'))
        raw_config.set('output', 'precursor accuracy left', raw_config.get('search', 'precursor accuracy left'))
        raw_config.set('output', 'precursor accuracy right', raw_config.get('search', 'precursor accuracy right'))
        raw_config.set('missed cleavages', 'protease1', raw_config.get('search', 'enzyme'))
        raw_config.set('missed cleavages', 'number of missed cleavages', raw_config.get('search', 'number of missed cleavages'))
        raw_config.set('fragment mass', 'mass accuracy', raw_config.get('search', 'product accuracy'))
        raw_config.set('charges', 'min charge', raw_config.get('search', 'minimum charge'))
        raw_config.set('charges', 'max charge', raw_config.get('search', 'maximum charge'))
        raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))
        self.parameters.add(paramobj)
        self.save()

    def get_searchruns(self):
        return self.searchrun_set.filter(union=False)
        # return self.searchruns.filter(union=False)

    def get_union(self):
        return self.searchrun_set.filter(union=True)
        # return self.searchruns.filter(union=True)

    def get_searchruns_all(self):
        return self.searchrun_set.all().order_by('union')
        # return self.searchruns.all().order_by('union')

    def name(self):
        return os.path.split(self.groupname)[-1]

    def change_status(self, message):
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
        self.add_spectra(c['chosenspectra'])
        self.add_fasta(c['chosenfasta'])
        self.add_params(c['SearchParametersForm'])

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
        custom_order = ['sumi',
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
        all_images = [doc for doc in self.resimagefiles.all()]
        all_images.sort(key=lambda val: custom_order.index(val.docfile.name.encode('ASCII').split('_')[-1].replace('.png', '').lower()))
        return all_images

    def get_pepxmlfiles(self):
        return self.pepxmlfiles.all()

    def get_pepxmlfiles_paths(self):
        return [pep.docfile.name.encode('ASCII') for pep in self.pepxmlfiles.all()]

    def get_spectrafiles_paths(self):
        return [pep.docfile.name.encode('ASCII') for pep in self.spectra.all()]

    def get_fastafile_path(self):
        return [self.fasta.all()[0].docfile.name.encode('ASCII'), ]

    def get_resimage_paths(self):
        return [pep.docfile.name.encode('ASCII') for pep in self.get_resimagefiles()]

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
        from pyteomics import mgf, pepxml, mzml
        import csv
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