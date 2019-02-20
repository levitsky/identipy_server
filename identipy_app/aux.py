import matplotlib
matplotlib.use('Agg')
import os
import sys
import csv
import numpy as np
import pandas as pd
import pylab
from io import BytesIO
import base64
from urllib import quote_plus
from time import time

from django.core.files import File
from django.conf import settings
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.utils import html

from pyteomics import auxiliary as aux, pylab_aux
sys.path.insert(0, '../identipy/')
from identipy.utils import CustomRawConfigParser
os.chdir(settings.BASE_DIR)
csv.field_size_limit(10000000)


def get_LFQ_dataframe(inputfile, lfq_type='NSAF'):
    # lfq_type from ['NSAF', 'SIn', 'emPAI']:
    dframe = pd.read_table(inputfile)
    dframe.index = dframe['dbname']
    label = '_' + os.path.basename(inputfile).replace('_proteins.tsv', '')
    dframe[lfq_type + label] = dframe['LFQ(%s)' % (lfq_type, )]
    dframe = dframe[[lfq_type + label]]
    return dframe

def concat_LFQ_tables(filenames):
    return pd.concat([get_LFQ_dataframe(f) for f in filenames], axis=1)

def convert_linear(dfout):
    ref_col = None
    ref_min_val = None
    for col in dfout.columns:
        calc_na = dfout[col].isna().sum()
        if not ref_col or calc_na < ref_min_val:
            ref_col = col
            ref_min_val = calc_na

    for col in dfout.columns:
        if col != ref_col:
            dftmp = dfout[[col, ref_col]].dropna()
            a, b, R, sigma = aux.linear_regression(dftmp[col], dftmp[ref_col])
            dfout[col] = dfout[col].apply(lambda x: x * a + b)
    return dfout

def fill_missing_values(dfout):
    min_lfq_dict = dict()
    for col in dfout.columns:
        min_lfq_dict[col] = dfout[col].min()
    dfout = dfout.fillna(value=min_lfq_dict)
    return dfout

def process_LFQ(filenames, outpath):
    dframe = concat_LFQ_tables(filenames)
    dframe = convert_linear(dframe)
    dframe = fill_missing_values(dframe)
    dframe.to_csv(path_or_buf=outpath, sep='\t', encoding='utf-8')

def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return float(total_size)

def save_mods(uid, chosenmods, fixed, paramtype=3):
    import models
    paramobj = models.ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % paramtype, user=uid)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name)
    labels = ','.join(mod.get_label() for mod in chosenmods)
#   print 'LABELS:', labels
    raw_config.set('modifications', 'fixed' if fixed else 'variable', labels + '|type>string')
    for mod in chosenmods:
        raw_config.set('modifications', mod.label, mod.mass)
    with open(paramobj.docfile.name, 'w') as f:
        raw_config.write(f)

def save_params_new(sfForms, uid, paramsname=False, paramtype=3, request=False, visible=True):
    from models import ParamsFile, Protease
    paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_{}.cfg'.format(paramtype),
            user=uid, type=paramtype)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name)
    if request:
        sfForms = {}
        for sftype in ['main', 'postsearch']:
            sfForms[sftype] = SearchParametersForm(request.POST, raw_config=raw_config,
                    user=request.user, label_suffix='', sftype=sftype, prefix=sftype)
    for sf in sfForms.values():
        SearchParametersForm_values = {v.name: v.value() or '' for v in sf}
        for section in raw_config.sections():
            for param in raw_config.items(section):
                if param[0] in SearchParametersForm_values:
                    orig_choices = raw_config.get_choices(section, param[0])
                    if orig_choices == 'type>boolean':
                        tempval = ('1' if SearchParametersForm_values[param[0]] else '0')
                    else:
                        tempval = SearchParametersForm_values[param[0]]
                    raw_config.set(section, param[0], tempval + '|' + orig_choices)
    enz = raw_config.get('search', 'enzyme')
    protease = Protease.objects.filter(user=uid, rule=enz).first()
    raw_config.set('search', 'enzyme', protease.name + '|' + raw_config.get_choices('search', 'enzyme'))
    if raw_config.getboolean('options', 'use auto optimization'):
        raw_config.set('misc', 'first stage', 'identipy.extras.optimization')
    else:
        raw_config.set('misc', 'first stage', '')
    raw_config.set('output', 'precursor accuracy unit', raw_config.get('search', 'precursor accuracy unit'))
    raw_config.set('output', 'precursor accuracy left', raw_config.get('search', 'precursor accuracy left'))
    raw_config.set('output', 'precursor accuracy right', raw_config.get('search', 'precursor accuracy right'))
    raw_config.set('missed cleavages', 'protease1', raw_config.get('search', 'enzyme'))
    raw_config.set('missed cleavages', 'number of missed cleavages',
            raw_config.get('search', 'number of missed cleavages'))
    raw_config.set('fragment mass', 'mass accuracy', raw_config.get('search', 'product accuracy'))
    raw_config.set('charges', 'min charge', raw_config.get('search', 'minimum charge'))
    raw_config.set('charges', 'max charge', raw_config.get('search', 'maximum charge'))

    if paramsname:
        paramobj = ParamsFile(user=uid, type=paramtype, visible=visible, title=paramsname)
        paramobj.save()
        fl = open('{}.cfg'.format(paramobj.id), 'w')
        fl.close()
        fl = open('{}.cfg'.format(paramobj.id))
        djangofl = File(fl)
        paramobj.docfile = djangofl
        paramobj.save()
        fl.close()
        os.remove(fl.name)
    raw_config.write(open(paramobj.docfile.name, 'w'))
    return paramobj

class ResultsDetailed():
    def __init__(self, ftype, path_to_csv, runid):
        from .models import SearchRun
        self.ftype = ftype
        self.order_by_revers = False
        self.runid = runid
        self.union = get_object_or_404(SearchRun, pk=runid).union
        with open(path_to_csv) as cf:
            reader = csv.reader(cf, delimiter='\t')
            self.labels = reader.next()
            if self.labels[-1] == 'is decoy':
                self.labels = self.labels[:-1]
                rmvlast = True
            else:
                rmvlast = False
            self.whiteind = [True for _ in range(len(self.labels))]
            self.order_by_label = self.labels[0]
            if rmvlast:
                self.values = [val[:-1] for val in reader]
            else:
                self.values = [val for val in reader]
            self.dbname = False

    def special_links(self, value, name, dbname):
        from . import forms
        types = {'PSMs': 'psm', 'peptides': 'peptide'}
        if self.ftype == 'protein' and name == 'dbname':
            try:
                return '<a target="_blank" href="http://www.uniprot.org/uniprot/%s">%s</a>' % (
                        html.escape(name).split('|')[1], html.escape(value))
            except IndexError:
                return html.escape(value)
        elif self.ftype == 'protein' and name == 'description':
            return '<a target="_blank" href="http://www.ncbi.nlm.nih.gov/pubmed/?term=%s">%s</a>' % (
                    html.escape(name.split('OS=')[0]), html.escape(name))
        elif self.ftype == 'protein' and name in types:
            return '<a class="td2" class="link" href="%s?dbname=%s&show_type=%s&runid=%s">%s</a>' % (
                    reverse("identipy_app:show"), dbname, types[name], self.runid, value)
        elif self.ftype == 'peptide' and name == 'sequence':
            return '<a class="td2" class="link" href="%s?dbname=%s&show_type=%s&runid=%s">%s</a>' % (reverse("identipy_app:show"), dbname, 'psm', self.runid, value)
        elif name == 'spectrum' and not self.union:
            return r'<a class="td2 link" href="{}?runid={}&spectrum={}">{}</a>'.format(reverse('identipy_app:spectrum'),
                    self.runid, quote_plus(value), value)
        else:
            return value

    def filter_dbname(self, dbname):
        self.dbname = dbname

    def custom_labels(self, whitelist):
        for idx, label in enumerate(self.labels):
            self.whiteind[idx] = label in whitelist

    def change_order(self, order_reverse):
        self.order_by_revers = order_reverse
        # self.order_by_revers = not self.order_by_revers

    def custom_order(self, order_by_label=False, order_reverse=False):
        self.change_order(order_reverse)
        sort_ind = self.labels.index(order_by_label.replace(u'\xa0', ' '))
        try:
            self.values.sort(key=lambda x: float(x[sort_ind]))
        except:
            self.values.sort(key=lambda x: x[sort_ind])
        if self.order_by_revers:
            self.values = self.values[::-1]

    def get_labels(self):
        return [label for idx, label in enumerate(self.labels) if self.whiteind[idx]]

    def get_values(self, rawformat=False):
        if self.dbname:
            dbname_ind = self.labels.index('proteins')
            sequence_ind = self.labels.index('sequence')
        for val in self.values:
            if not self.dbname or self.dbname in [xz.strip() for xz in val[dbname_ind].split(';')] or self.dbname == val[sequence_ind]:
                out = []
                for idx, v in enumerate(val):
                    if self.whiteind[idx]:
                        if rawformat:
                            out.append(v)
                        else:
                            out.append(mark_safe(self.special_links(v, self.labels[idx], val[0])))
                yield out

def spectrum_figure(*args, **kwargs):
    pylab_aux.annotate_spectrum(*args, **kwargs)
    figfile = BytesIO()
    pylab.tight_layout()
    pylab.savefig(figfile, format='svg')
    data = base64.b64encode(figfile.getvalue())
    return data
