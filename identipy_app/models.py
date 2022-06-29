from django.db import models
from django.contrib.auth.models import User as BaseUser
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os
import shutil
import subprocess
import psutil
import configparser
import re
import logging
logger = logging.getLogger(__name__)

# from . import aux

os.chdir(settings.BASE_DIR)

from identipy.utils import CustomRawConfigParser
from identipy import main, utils


class User(BaseUser):
    latest_params = models.ForeignKey('SearchParameters', on_delete=models.SET_NULL, related_name='+', null=True)


def kill_proc_tree(pid, including_parent=True):
    logger.debug('Trying to kill tree %s, including parent: %s', pid, including_parent)
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess as e:
        logger.warn('No such process: %s', e.args[0])
        return
    for child in children:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            logger.warning('No such process (child): %s', child.pid)
        else:
            logger.debug('Successfully killed child: %s', child.pid)
    psutil.wait_procs(children, timeout=5)
    if including_parent:
        try:
            parent.kill()
            parent.wait(5)
        except psutil.NoSuchProcess:
            logger.warning('No such process (parent): %s', parent.pid)
        else:
            logger.debug('Successfully killed parent: %s', parent.pid)


class BaseDocument(models.Model):
    date_added = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

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
    docfile = models.FileField(upload_to=upload_to_spectra, max_length=200)


class FastaFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_fasta, max_length=200)


class RawFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_raw, max_length=200)


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return os.path.join(settings.MEDIA_ROOT, name)#name


class ParamsFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_params, max_length=200)
    type = models.IntegerField(default=3)
    visible = models.BooleanField(default=True)
    title = models.CharField(max_length=80, default='')


class Protease(models.Model):
    name = models.CharField(max_length=80)
    rule = models.CharField(max_length=80)
    order_val = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('name', 'user')

    def __str__(self):
        return self.name


class Modification(models.Model):
    name = models.CharField(max_length=80)
    label = models.CharField(max_length=30)
    aminoacid = models.CharField(max_length=2)
    mass = models.FloatField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('name', 'user', 'aminoacid', 'mass', 'label')

    def get_label(self):
        if self.aminoacid == '[':
            return self.label + '-'
        if self.aminoacid == ']':
            return '-' + self.label
        return self.label + self.aminoacid

    def __str__(self):
        return self.name


class SearchParameters(models.Model):
    title = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    send_email_notification = models.BooleanField(default=False)
    use_auto_optimization = models.BooleanField(default=True)
    fdr = models.FloatField('FDR level, %', default=1.0)
    PPM = 'P'
    DA = 'D'
    MASS_UNITS = ((PPM, 'ppm'), (DA, 'Da'))
    precursor_accuracy_unit = models.CharField(max_length=1, default=PPM, choices=MASS_UNITS)
    precursor_accuracy_left = models.FloatField(default=10.)
    precursor_accuracy_right = models.FloatField(default=10.)
    product_accuracy = models.FloatField(default=0.1, help_text='Product ion accuracy in Th')
    product_minimum_mz = models.FloatField('product minimum m/z', default=150)
    peptide_maximum_length = models.PositiveSmallIntegerField(default=50)
    peptide_minimum_length = models.PositiveSmallIntegerField(default=5)
    peptide_maximum_mass = models.FloatField(default=10000)
    peptide_minimum_mass = models.FloatField(default=300)
    proteases = models.ManyToManyField(Protease)
    number_of_missed_cleavages = models.PositiveSmallIntegerField(default=2)
    maximum_charge = models.PositiveSmallIntegerField(default=3)
    minimum_charge = models.PositiveSmallIntegerField(default=2)
    precursor_isotope_mass_error = models.PositiveSmallIntegerField(default=0)
    mass_shifts = models.CharField(max_length=80, blank=True,
        help_text='A set of mass shifts to apply to all peptides for matching. '
        'Example: 0, 16.000, 23.000')
    snp = models.BooleanField(default=False, help_text='make SNP changes for ALL peptides')
    protein_cterm_cleavage = models.FloatField(default=17.002735)
    protein_nterm_cleavage = models.FloatField(default=1.007825)
    fixed_modifications = models.ManyToManyField(Modification, related_name='+', blank=True)
    variable_modifications = models.ManyToManyField(Modification, related_name='+', blank=True)
    maximum_variable_mods = models.PositiveSmallIntegerField(default=2)
    add_decoy = models.BooleanField(default=False)
    decoy_prefix = models.CharField(max_length=20, blank=True, default='DECOY_')
    REVERSE = 'R'
    SHUFFLE = 'S'
    DECOY_METHODS = ((REVERSE, 'reverse'), (SHUFFLE, 'shuffle'))
    decoy_method = models.CharField(max_length=1, default=REVERSE, choices=DECOY_METHODS)
    minimum_peaks = models.PositiveSmallIntegerField(default=4)
    maximum_peaks = models.PositiveSmallIntegerField(default=50)
    dynamic_range = models.FloatField(default=100.)
    maximum_fragment_charge = models.PositiveSmallIntegerField(default=0)
    deisotope = models.BooleanField(default=True)
    deisotoping_mass_tolerance = models.FloatField(default=0.3)

    field_names = [
        ('send_email_notification', ('options', 'send email notification')),
        ('use_auto_optimization', ('options', 'use auto optimization')),
        ('fdr', ('options', 'FDR')),
        ('precursor_accuracy_unit', ('search', 'precursor accuracy unit')),
        ('precursor_accuracy_left', ('search', 'precursor accuracy left')),
        ('precursor_accuracy_right', ('search', 'precursor accuracy right')),
        ('product_accuracy', ('search', 'product accuracy')),
        ('product_minimum_mz', ('search', 'product minimum m/z')),
        ('peptide_maximum_length', ('search', 'peptide maximum length')),
        ('peptide_minimum_length', ('search', 'peptide minimum length')),
        ('peptide_maximum_mass', ('search', 'peptide maximum mass')),
        ('peptide_minimum_mass', ('search', 'peptide minimum mass')),
        ('proteases', ('search', 'enzyme')),
        ('maximum_charge', ('search', 'maximum charge')),
        ('minimum_charge', ('search', 'minimum charge')),
        ('precursor_isotope_mass_error', ('search', 'precursor isotope mass error')),
        ('mass_shifts', ('search', 'shifts')),
        ('snp', ('search', 'snp')),
        ('protein_cterm_cleavage', ('modifications', 'protein cterm cleavage')),
        ('protein_nterm_cleavage', ('modifications', 'protein nterm cleavage')),
        ('fixed_modifications', ('modifications', 'fixed')),
        ('variable_modifications', ('modifications', 'variable')),
        ('maximum_variable_mods', ('modifications', 'maximum variable mods')),
        ('add_decoy', ('input', 'add decoy')),
        ('decoy_prefix', ('input', 'decoy prefix')),
        ('decoy_method', ('input', 'decoy method')),
        ('minimum_peaks', ('scoring', 'minimum peaks')),
        ('maximum_peaks', ('scoring', 'maximum peaks')),
        ('dynamic_range', ('scoring', 'dynamic range')),
        ('maximum_fragment_charge', ('scoring', 'maximum fragment charge')),
        ('deisotope', ('input', 'deisotope')),
        ('deisotoping_mass_tolerance', ('input', 'deisotoping mass tolerance'))
    ]

    def to_str(self, field):
        value = getattr(self, field)

        if field in {'fixed_modifications', 'variable_modifications'}:
            return ', '.join(m.get_label() for m in value.all())
        if field == 'proteases':
            return ','.join(p.rule for p in value.all())
        if self._meta.get_field(field).choices:
            return getattr(self, f'get_{field}_display')()
        return str(value)

    def write_config(self, fname):
        config = self.create_config()
        with open(fname, 'w') as f:
            config.write(f)

    def create_config(self):
        config = configparser.ConfigParser()
        for (field, (section, option)) in self.field_names:
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, option, self.to_str(field))
        return config

    field_types = {
        'BooleanField': lambda c, s, o: c.getboolean(s, o),
        'FloatField': lambda c, s, o: c.getfloat(s, o),
        'PositiveSmallIntegerField': lambda c, s, o: c.getint(s, o),
    }

    @classmethod
    def get_field_converter(cls, field, user):
        if field == 'proteases':
            return lambda c, s, o: [Protease.objects.filter(user=user, rule=x).first()
                for x in c.get(s, o).split(',')]
        if field in {'fixed_modifications', 'variable_modifications'}:
            def f(c, s, o):
                mods = []
                for x in re.split(r',\s*', c.get(s, o)):
                    if x:
                        mod, aa, term = utils.custom_split_label(x)
                        if aa == '-':
                            aa = term
                        mods.append(Modification.objects.get(user=user, aminoacid=aa, label=mod))
                return mods
            return f
        choices = cls._meta.get_field(field).choices
        if choices:
            def f(c, s, o):
                value = c.get(s, o)
                for raw, label in choices:
                    if value == label:
                        return raw
            return f
        field_type = cls._meta.get_field(field).get_internal_type()
        return cls.field_types.get(field_type, lambda c, s, o: c.get(s, o))

    @classmethod
    def read_file(cls, f, user):
        config = configparser.ConfigParser(allow_no_value=True,
            inline_comment_prefixes=(';', '#'))
        config.read_file(f)
        data = {}
        for (field, (section, option)) in cls.field_names:
            try:
                data[field] = cls.get_field_converter(field, user)(config, section, option)
            except (configparser.NoOptionError, configparser.NoSectionError) as e:
                logger.warning('Could not set field %s: %s', field, e)
        data['user'] = user
        fmods = data.pop('fixed_modifications')
        vmods = data.pop('variable_modifications')
        proteases = data.pop('proteases')
        instance = cls(**data)
        instance.save()
        instance.fixed_modifications.set(fmods)
        instance.variable_modifications.set(vmods)
        instance.proteases.set(proteases)
        return instance


class SearchGroup(models.Model):
    groupname = models.CharField(max_length=80, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)
    fasta = models.ManyToManyField(FastaFile)
    parameters = models.ForeignKey(SearchParameters, null=True, blank=True, on_delete=models.SET_NULL)
    notification = models.BooleanField(default=False)
    fdr_level = models.FloatField(default=0.0)

    def get_status(self):
        runs = self.searchrun_set.all()
        if len(runs) == 1:
            return runs[0].get_status_display()
        union = self.searchrun_set.get(union=True)
        dead = sum(r.status == SearchRun.DEAD for r in runs)
        if dead:
            return '{} process(es) dead'.format(dead)
        error = union.status == SearchRun.ERROR
        if error:
            return 'Finished with errors'
        validation = union.status == SearchRun.RUNNING
        if validation:
            return 'Postsearch processing'
        done = sum(r.status == SearchRun.FINISHED for r in runs)
        if done == len(runs):
            return 'Finished'
        if done:
            return '{} of {} done'.format(done, len(runs))
        done = sum(r.status == SearchRun.VALIDATION and not r.union for r in runs)
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
        self.add_params(c['params'])
        self.add_fasta(c['chosenfasta'])
        for sid in c['chosenspectra']:
            s = SpectraFile.objects.get(pk=sid)
            newrun = SearchRun(searchgroup=self, status=SearchRun.WAITING,
                    runname=os.path.splitext(s.docfile.name)[0], spectra=s)
            newrun.save()
            self.save()
        if len(c['chosenspectra']) > 1:
            newrun = SearchRun(searchgroup=self, runname='union', union=True, status=SearchRun.WAITING)
            newrun.save()
            self.save()

    def add_params(self, params):
        params.pk = None
        params.save()
        self.parameters = params
        self.save()

    def add_fasta(self, fastaobject):
        self.fasta.add(fastaobject[0])
        self.save()

    def get_searchruns(self):
        return self.searchrun_set.filter(union=False)

    def get_searchruns_all(self):
        return self.searchrun_set.all().order_by('union')

    def name(self):
        return os.path.split(self.groupname)[-1]

    def full_delete(self):
        for sr in self.get_searchruns_all():
            if sr.status == SearchRun.RUNNING:
                kill_proc_tree(sr.processpid)
            logger.info('Deleting run %s', sr.pk)
        tree = self.dirname()
        try:
            shutil.rmtree(tree)
        except Exception:
            logger.warning('Could not remove tree: %s', tree)
        self.delete()

    def set_notification(self):
        settings = main.settings(self.parameters.path())
        self.notification = settings.getboolean('options', 'send email notification')
        self.save()

    def set_FDR(self):
        raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True, inline_comment_prefixes=(';', '#'))
        raw_config.read(self.parameters.path())
        self.fdr_level = raw_config.getfloat('options', 'FDR')
        self.save()

    def dirname(self):
        return 'results/{}/{}'.format(self.user.id, self.id)


class SearchRun(models.Model):
    searchgroup = models.ForeignKey(SearchGroup, on_delete=models.CASCADE)
    runname = models.CharField(max_length=80)
    spectra = models.ForeignKey(SpectraFile, blank=True, null=True, on_delete=models.SET_NULL)
    processpid = models.IntegerField(blank=True, default=-1)
    numMSMS = models.BigIntegerField(default=0)
    totalPSMs = models.BigIntegerField(default=0)
    numPSMs = models.BigIntegerField(default=0)
    numPeptides = models.BigIntegerField(default=0)
    numProteins = models.BigIntegerField(default=0)
    numProteinGroups = models.BigIntegerField(default=0)
    union = models.BooleanField(default=False)

    WAITING = 'W'
    RUNNING = 'R'
    VALIDATION = 'V'
    FINISHED = 'F'
    DEAD = 'D'
    ERROR = 'E'
    STATUS_CHOICES = (
            (WAITING, 'Waiting'),
            (RUNNING, 'Running'),
            (VALIDATION, 'Postsearch processing'),
            (FINISHED, 'Finished'),
            (DEAD, 'Dead'),
            (ERROR, 'Error'),
            )
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=DEAD)
    last_update = models.DateTimeField(auto_now=True)


    def add_spectra(self, spectraobject):
        self.spectra = spectraobject
        self.save()

    def get_pepxmlfiles(self, filtered=False):
        if self.union and not filtered:
            return PepXMLFile.objects.filter(run__searchgroup=self.searchgroup, run__union=False, filtered=False)
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

    def name(self):
        return os.path.split(self.runname)[-1]

    def calc_results(self):
        from pyteomics import mgf, mzml
        for fn in self.get_spectrafiles_paths():
            if fn.lower().endswith('.mgf'):
                try:
                    msmsnum = int(subprocess.check_output(['grep', '-c', 'BEGIN IONS', '%s' % (fn, )]))
                except:
                    msmsnum = sum(1 for _ in mgf.read(fn))
            elif fn.lower().endswith('.mzml'):
                msmsnum = sum(1 for _ in mzml.read(fn))
            self.numMSMS += msmsnum

        for fn in self.rescsv_set.filter(ftype='psm', filtered=False):
            with open(fn.docfile.name) as cf:
                self.totalPSMs += sum(1 for _ in cf) - 1
        for fn in self.rescsv_set.filter(ftype='psm', filtered=True):
            with open(fn.docfile.name) as cf:
                self.numPSMs += sum(1 for _ in cf) - 1
        for fn in self.rescsv_set.filter(ftype='peptide', filtered=True):
            with open(fn.docfile.name) as cf:
                self.numPeptides += sum(1 for _ in cf) - 1
        for fn in self.rescsv_set.filter(ftype='protein', filtered=True):
            with open(fn.docfile.name) as cf:
                self.numProteins += sum(1 for _ in cf) - 1
        for fn in self.rescsv_set.filter(ftype='prot_group', filtered=True):
            with open(fn.docfile.name) as cf:
                self.numProteinGroups += sum(1 for _ in cf) - 1
        self.save()


class PepXMLFile(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage(), max_length=200)
    filtered = models.BooleanField(default=False)
    run = models.ForeignKey(SearchRun, on_delete=models.CASCADE)


class ResImageFile(BaseDocument):
    docfile = models.ImageField(upload_to=upload_to_pepxml, storage=OverwriteStorage(), max_length=200)
    ftype = models.CharField(max_length=5, default='.png')
    PSM = 'S'
    PEPTIDE = 'P'
    PROTEIN = 'R'
    OTHER = 'O'
    IMAGE_TYPES = (
            (PSM, 'PSM'),
            (PEPTIDE, 'Peptide'),
            (PROTEIN, 'Protein'),
            (OTHER, 'Feature'),
            )
    imgtype = models.CharField(max_length=1, default=OTHER, choices=IMAGE_TYPES)
    run = models.ForeignKey(SearchRun, on_delete=models.CASCADE)


class ResCSV(BaseDocument):
    docfile = models.FileField(upload_to=upload_to_pepxml, storage=OverwriteStorage(), max_length=200)
    ftype = models.CharField(max_length=10)
    filtered = models.BooleanField(default=True)
    run = models.ForeignKey(SearchRun, on_delete=models.CASCADE)
