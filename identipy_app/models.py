# -*- coding: utf-8 -*-
from django.db import models, connection
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os
from django.conf import settings
import sys
import shutil
import subprocess
import psutil, os
import csv
import logging
logger = logging.getLogger(__name__)

from . import aux

os.chdir(settings.BASE_DIR)
sys.path.insert(0, '../identipy/')
from identipy.utils import CustomRawConfigParser
from identipy import main


def kill_proc_tree(pid, including_parent=True):
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    for child in children:
        child.kill()
    psutil.wait_procs(children, timeout=5)
    if including_parent:
        parent.kill()
        parent.wait(5)

class BaseDocument(models.Model):
    date_added = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User)

    def name(self):
        return os.path.split(self.docfile.name)[-1]

    def path(self):
        return os.path.join(settings.MEDIA_ROOT, self.docfile.name)

    def customdel(self):
        os.remove(self.path())
        self.delete()

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

def upload_to_params(instance, filename):
    return upload_to_basic('params', filename, instance.user.id)

 
class SpectraFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_spectra)


class FastaFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_fasta)


class RawFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_raw)


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return os.path.join(settings.MEDIA_ROOT, name)#name


class ParamsFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_params)
    type = models.IntegerField(default=3)
    visible = models.BooleanField(default=True)


class SearchGroup(models.Model):
    groupname = models.CharField(max_length=80, default='')
    user = models.ForeignKey(User)
    date_added = models.DateTimeField(auto_now_add=True)
    fasta = models.ManyToManyField(FastaFile)
    parameters = models.ForeignKey(ParamsFile, null=True, blank=True)
    notification = models.BooleanField(default=False)
    fdr_level = models.FloatField(default=0.0)

    PSM = 'S'
    PEPTIDE = 'P'
    PROTEIN = 'R'
    FDR_TYPES = (
            (PSM, 'PSM'),
            (PEPTIDE, 'peptide'),
            (PROTEIN, 'protein')
            )
    fdr_type = models.CharField(max_length=1, default=PSM, choices=FDR_TYPES)
 
    def get_status(self):
        runs = self.searchrun_set.all()
        if len(runs) == 1:
            return runs[0].get_status_display()
        dead = sum(r.status == SearchRun.DEAD for r in runs)
        if dead:
            return '{} process(es) dead'.format(dead)
        done = sum(r.status == SearchRun.FINISHED for r in runs)
        if done == len(runs):
            return 'Finished'
        if done:
            return '{} of {} done'.format(done, len(runs))
        started = sum(r.status == SearchRun.RUNNING for r in runs)
        if started:
            return '{} of {} started'.format(started, len(runs))
        if all(r.status == SearchRun.WAITING for r in runs):
            return 'Waiting'
        return 'Could not determine status'

    def get_last_update(self):
        return self.searchrun_set.latest('last_update').last_update

    def add_files(self, c):
        self.add_fasta(c['chosenfasta'])
        self.add_params(sfForms=c['SearchForms'], paramtype=c['paramtype'])
        self.save()
        for sid in c['chosenspectra']:
            s = SpectraFile.objects.get(pk=sid)
            newrun = SearchRun(searchgroup=self, status=SearchRun.WAITING,
                    runname=os.path.splitext(s.docfile.name)[0], spectra=s)
            newrun.save()
            newrun.save()
            self.save()
        if len(c['chosenspectra']) > 1:
            newrun = SearchRun(searchgroup=self, runname='union', union=True, status=SearchRun.WAITING)
            newrun.save()
            self.save()

    def add_fasta(self, fastaobject):
        self.fasta.add(fastaobject[0])
        self.save()

    def add_params(self, sfForms, paramtype=3):
        paramobj = aux.save_params_new(sfForms=sfForms, uid=self.user,
                paramsname=self.groupname, paramtype=paramtype, request=False, visible=False)
        self.parameters = paramobj
        self.save()

    def get_searchruns(self):
        return self.searchrun_set.filter(union=False)

    def get_union(self):
        return self.searchrun_set.get(union=True)

    def get_searchruns_all(self):
        return self.searchrun_set.all().order_by('union')

    def name(self):
        return os.path.split(self.groupname)[-1]

    def full_delete(self):
        for sr in self.get_searchruns_all():
            if sr.status == SearchRun.RUNNING:
                kill_proc_tree(sr.processpid)
            logger.info('Deleting run %s', sr.pk)
        tree = 'results/%s/%s' % (str(self.user.id), self.id)
        try:
            shutil.rmtree(tree)
        except Exception:
            logger.warning('Could not remove tree: %s', tree)
        self.delete()

    def set_notification(self):
        settings = main.settings(self.parameters.path())
        self.notification = settings.getboolean('options', 'send email notification')
        self.save()

    def set_FDRs(self):
        raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
        raw_config.read(self.parameters.path())
        self.fdr_level = raw_config.getfloat('options', 'FDR')
        types = {v.lower(): k for k, v in self.FDR_TYPES}
        try:
            self.fdr_type = types[raw_config.get('options', 'FDR_type').lower()]
        except KeyError as e:
            logger.error('Incorrect FDR type: %s', e.args)
            self.fdr_type = self.PSM
        self.save()


class SearchRun(models.Model):
    searchgroup = models.ForeignKey(SearchGroup)

    runname = models.CharField(max_length=80)
    spectra = models.ForeignKey(SpectraFile, blank=True, null=True)
    processpid = models.IntegerField(blank=True, default=-1)
    numMSMS = models.BigIntegerField(default=0)
    totalPSMs = models.BigIntegerField(default=0)
    numPSMs = models.BigIntegerField(default=0)
    numPeptides = models.BigIntegerField(default=0)
    numProteins = models.BigIntegerField(default=0)
    union = models.BooleanField(default=False)

    WAITING = 'W'
    RUNNING = 'R'
    FINISHED = 'F'
    DEAD = 'D'
    STATUS_CHOICES = (
            (WAITING, 'Waiting'),
            (RUNNING, 'Running'),
            (FINISHED, 'Finished'),
            (DEAD, 'Dead'),
            )
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=DEAD)
    last_update = models.DateTimeField(auto_now=True)


    def add_spectra(self, spectraobject):
        # for s in spectraobjects:
        self.spectra = spectraobject
        self.save()


    def get_resimagefiles(self, ftype='.png'):
        def get_index(val, custom_list):
            for idx, v in enumerate(custom_list):
                if val == v or (v == 'potential_modifications' and val.startswith(v)):
                    return idx

        custom_order = ['RT_experimental',
                        'precursor_mass',
                        'peptide_length',
                        'RT_experimental_peptides',
                        'precursor_mass_peptides',
                        'peptide_length_peptides',
                        'sumi',
                        'nsaf',
                        'empai',
                        'rt_difference_min',
                        'precursor_mass difference_ppm',
                        'fragment_mass_tolerance_da',
                        'potential_modifications',
                        'isotopes_mass_difference_da',
                        'missed_cleavages_protease_1',
                        'psm_count',
                        'psms_per_protein',
                        'charge_states',
                        'scores']
        all_images = [doc for doc in self.resimagefile_set.filter(ftype=ftype)]
        all_images.sort(key=lambda val: get_index(val.docfile.name.split('/')[-1].replace(self.runname.split('/')[-1] + '_', '').replace(ftype, '').lower(), custom_order))
        return all_images
    
    def get_PSMdistrimagefiles(self, ftype='.png'):
        distr_list = {'rt_experimental', 'precursor_mass', 'peptide_length'}
        distr_images = [doc for doc in self.get_resimagefiles()
                if doc.docfile.name.split('/')[-1].replace(
                    self.runname.split('/')[-1] + '_', '').replace(ftype, '').lower() in distr_list]
        return distr_images

    def get_distrimagefiles(self, ftype='.png'):
        distr_list = {'rt_experimental_peptides', 'precursor_mass_peptides', 'peptide_length_peptides'}
        distr_images=[doc for doc in self.get_resimagefiles() if doc.docfile.name.split('/')[-1].replace(self.runname.split('/')[-1] + '_', '').replace(ftype, '').lower() in distr_list]
        return distr_images
    
    def get_quantimagefiles(self, ftype='.png'):
        quant_list = {'sumi', 'nsaf', 'empai'}
        quant_images=[doc for doc in self.get_resimagefiles() if doc.docfile.name.split('/')[-1].replace(self.runname.split('/')[-1] + '_', '').replace(ftype, '').lower() in quant_list]
        return quant_images
    
    def get_mpimagefiles(self, ftype='.png'):
        MP_list = ['rt_difference_min',
                   'precursor_mass_difference_ppm',
                   'fragment_mass_tolerance_da',
                   'isotopes_mass_difference_da',
                   'missed_cleavages_protease_1',
                   'psm_count',
                   'psms_per_protein',
                   'charge_states',
                   'scores']
        mp_images = [doc for doc in self.get_resimagefiles()
                if doc.docfile.name.split('/')[-1].replace(self.runname.split(
                    '/')[-1]  + '_', '').replace(ftype, '').lower() in MP_list or
                doc.docfile.name.split('/')[-1].replace(self.runname.split(
                    '/')[-1]  + '_', '').replace(ftype, '').lower().startswith('potential_modifications')]
        return mp_images
    
    def get_pepxmlfiles(self, filtered=False):
        if self.union:
            return PepXMLFile.objects.filter(run__searchgroup=self.searchgroup, run__union=False, filtered=filtered)
        return self.pepxmlfile_set.filter(filtered=filtered)

    def get_pepxmlfiles_paths(self, filtered=False):
        return [pep.docfile.name for pep in self.get_pepxmlfiles(filtered=filtered)]

    def get_spectrafiles_paths(self):
        if self.union:
            return [run.spectra.docfile.name for run in self.searchgroup.searchrun_set.filter(union=False)]
        return [self.spectra.docfile.name]


    def get_fastafile_path(self):
        return [self.searchgroup.fasta.all()[0].docfile.name]

    def get_resimage_paths(self, ftype='.png'):
        return [pep.docfile.name for pep in self.get_resimagefiles(ftype=ftype)]

    def get_csvfiles_paths(self, ftype=None):
        if ftype:
            return [pep.docfile.name for pep in self.rescsv_set.filter(ftype=ftype)]
        else:
            return [pep.docfile.name for pep in self.rescsv_set.all()]
  
    def name(self):
        return os.path.split(self.runname)[-1]

    def calc_results(self):
        from pyteomics import mgf, pepxml, mzml
        for fn in self.get_spectrafiles_paths():
            if fn.lower().endswith('.mgf'):
                try:
                    msmsnum = int(subprocess.check_output(['grep', '-c', 'BEGIN IONS', '%s' % (fn, )]))
                except:
                    msmsnum = sum(1 for _ in mgf.read(fn))
            elif fn.lower().endswith('.mzml'):
                msmsnum = sum(1 for _ in mzml.read(fn))
            self.numMSMS += msmsnum
        for fn in self.get_pepxmlfiles_paths():
            try:
                psmsnum = int(subprocess.check_output(['grep', '-c', '<spectrum_query', '%s' % (fn, )]))
            except:
                psmsnum = sum(1 for _ in pepxml.read(fn))
            self.totalPSMs += psmsnum
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


class PepXMLFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())
    filtered = models.BooleanField(default=False)
    run = models.ForeignKey(SearchRun)

class ResImageFile(BaseDocument):
    docfile = models.ImageField(upload_to=upload_to_pepxml, storage=OverwriteStorage())
    ftype = models.CharField(max_length=5, default='.png')
    run = models.ForeignKey(SearchRun)

class ResCSV(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage())
    ftype = models.CharField(max_length=10)
    run = models.ForeignKey(SearchRun)


class Protease(models.Model):
    name = models.CharField(max_length=80)
    rule = models.CharField(max_length=300, default='RK')
    order_val = models.IntegerField()
    user = models.ForeignKey(User)

    class Meta:
        unique_together = ('name', 'user')


class Modification(models.Model):
    name = models.CharField(max_length=80)
    label = models.CharField(max_length=30)
    aminoacid = models.CharField(max_length=2)
    mass = models.FloatField()
    user = models.ForeignKey(User)

    class Meta:
        unique_together = ('name', 'user', 'aminoacid', 'mass', 'label')

    def get_label(self):
        if self.aminoacid == '[':
            return self.label + '-'
        if self.aminoacid == ']':
            return '-' + self.label
        return self.label + self.aminoacid
