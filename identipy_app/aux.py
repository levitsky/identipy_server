import matplotlib
matplotlib.use('Agg')
import os
import csv
import pandas as pd
import pylab
from io import BytesIO
import base64
from urllib import quote_plus, urlencode
import ast

from django.core.files import File
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail

from pyteomics import auxiliary as aux, pylab_aux

from identipy import main, utils

os.chdir(settings.BASE_DIR)
csv.field_size_limit(10000000)

import logging
logger = logging.getLogger(__name__)

def get_LFQ_dataframe(inputfile, lfq_type='NSAF'):
    # lfq_type from ['NSAF', 'SIn', 'emPAI']:
    dframe = pd.read_csv(inputfile, sep='\t')
    dframe.index = dframe['dbname']
    label = '_' + os.path.basename(inputfile).replace('_proteins.tsv', '')
    dframe[lfq_type + label] = dframe[lfq_type]
    dframe = dframe[[lfq_type + label]]
    return dframe

def concat_LFQ_tables(filenames):
    return pd.concat([get_LFQ_dataframe(f) for f in filenames], axis=1, sort=True)

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
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
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
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
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

    _df_cache = {}

    def __init__(self, run, ftype, orderby=None, ascending=True, protein=None, peptide=None):
        self.ftype = ftype
        self.ascending = ascending
        self.run = run
        self.protein = protein
        self.peptide = peptide
        self._columns_mapping = {}
        if (run.id, ftype) in self._df_cache:
            self.df = self._df_cache[(run.id, ftype)]
            logger.debug('Reusing cached %s dataframe for run %s', ftype, run.id)
        else:
            path_to_csv = self.run.rescsv_set.get(ftype=ftype, filtered=True).docfile.name
            self.df = pd.read_csv(path_to_csv, sep='\t')
            logger.debug('Reading a new %s dataframe for run %s', ftype, run.id)
            self._format_columns()
            self._df_cache[(run.id, ftype)] = self.df
        if ftype in ['peptide', 'psm']:
            self.orderby = orderby or 'peptide'
            self.custom_labels(['peptide', 'calc_neutral_pep_mass', 'assumed_charge'])
        elif ftype in ['prot_group', 'protein']:
            self.orderby = orderby or 'dbname'
            self.custom_labels(['dbname', 'PSMs', 'peptides', 'sq', 'NSAF'])
        self._columns_mapping = dict((name.lstrip('_'), name) for name in self.df)

    @property
    def visible_columns(self):
        return self._columns_mapping.keys()

    def backup(self, colname):
        self.df['__' + colname] = self.df[colname]
        self._columns_mapping[colname] = '__' + colname

    def _format_columns(self):
        types = {'PSMs': 'psm', 'peptides': 'peptide'}
        show_url = reverse("identipy_app:show")
        # this uses the raw dbname and must be run first
        for col, t in types.items():
            if col in self.df:
                self.backup(col)
                self.df[col] = self.df.apply(
                    lambda row: '<a class="td2 link" href="{}?dbname={}&show_type={}&runid={}">{}</a>'.format(
                        show_url, row['dbname'], t, self.run.id, row[col]),
                    axis=1,
                )
        if 'dbname' in self.df:
            self.backup('dbname')
            self.df['dbname'] = self.df.dbname.apply(
                lambda value: '<a target="_blank" href="http://www.uniprot.org/uniprot/{}">{}</a>'.format(
                        value.split('|')[1], value))
        if 'protein_descr' in self.df:
            self.df['protein_descr'] = self.df['protein_descr'].apply(
                lambda value: ', '.join('<a target="_blank" href="http://www.ncbi.nlm.nih.gov/pubmed/?term={}">{}</a>'.format(
                    v.split('OS=')[0], v) for v in ast.literal_eval(value)))
        if 'description' in self.df:
            self.df['description'] = self.df['description'].apply(
                lambda v: '<a target="_blank" href="http://www.ncbi.nlm.nih.gov/pubmed/?term={}">{}</a>'.format(
                    v.split('OS=')[0], v))
        if 'peptide' in self.df:
            self.backup('peptide')
            self.df.peptide = self.df.peptide.apply(
                lambda value: '<a class="td2 link" href="{}?&show_type=psm&runid={}&peptide={}">{}</a>'.format(
                    show_url, self.run.id, value, value))
        if 'spectrum' in self.df and not self.run.union:
            self.backup('spectrum')
            self.df.spectrum = self.df.spectrum.apply(
                lambda value: '<a class="td2 link" href="{}?runid={}&spectrum={}">{}</a>'.format(
                    reverse('identipy_app:spectrum'), self.run.id, quote_plus(value), value))
        if 'protein' in self.df:
            self.backup('protein')
            self.df.protein = self.df.protein.apply(
                lambda value: ', '.join(
                    '<a class="td2 link" href="{}?dbname={}&show_type={}&runid={}">{}</a>'.format(
                        show_url, v, self.ftype, self.run.id, v) for v in ast.literal_eval(value)))

    def _update_headers(self, df):
        headers_mapping = {}
        show_url = reverse("identipy_app:show")
        params = {'show_type': self.ftype, 'runid': self.run.id}
        if self.protein:
            params['dbname'] = self.protein
        if self.peptide:
            params['peptide'] = self.peptide
        for visible, internal in list(self._columns_mapping.items()):
            if visible in df:
                params['reverse'] = int(visible == self.orderby and self.ascending)
                newheader = '<a class="th link" href="{}?{}&order_by={}">{}</a>'.format(show_url, urlencode(params), visible, visible)
                df[newheader] = df[visible]
                del df[visible]
                headers_mapping[visible] = newheader
        return headers_mapping

    def custom_labels(self, labels):
        self.labels = labels

    def get_labels(self):
        return self.labels

    def output_table(self, csv=False):
        condition = pd.Series(index=self.df.index, data=True)
        if self.protein:
            if 'protein' in self.df:
                prot = self.df['__protein']
            elif 'dbname' in self.df:
                prot = self.df['__dbname']
            condition = condition & prot.str.contains(self.protein, regex=False)
        if self.peptide:
            condition = condition & (self.df[self._columns_mapping['peptide']] == self.peptide)
        out = self.df.loc[condition, :].sort_values(by=self._columns_mapping[self.orderby], ascending=self.ascending)
        if csv:
            for c in out:
                if c in self.get_labels():
                    out[c] = out[self._columns_mapping[c]]
            return out[self.labels]

        return out

    def get_display(self):
        out = self.output_table()
        mapping = self._update_headers(out)
        with pd.option_context('display.max_colwidth', -1):
            return out.to_html(
                columns=[mapping[c] for c in self.labels], index=False, classes=('results_table',), escape=False)


def spectrum_figure(*args, **kwargs):
    pylab_aux.annotate_spectrum(*args, **kwargs)
    figfile = BytesIO()
    pylab.tight_layout()
    pylab.savefig(figfile, format='svg')
    data = base64.b64encode(figfile.getvalue())
    return data

def _copy_in_chunks(f, path):
    try:
        with open(path, 'wb') as ff:
            while True:
                chunk = f.read(5*1024*1024)
                if chunk:
                    ff.write(chunk)
                else:
                    break
    except IOError as e:
        logger.error('Error importing %s: %s', f.name, e.args)
    else:
        return path

def generated_db_path(sg):
    return os.path.join(sg.dirname(), 'generated.fasta')

def generate_database(sg):
    idsettings = main.settings(sg.parameters.path())
    fastafile = sg.fasta.all()[0].path()
    idsettings.set('input', 'database', fastafile)
    return utils.generate_database(idsettings, generated_db_path(sg))

def email_to_user(group):
    searchname = group.groupname
    username = group.user.email
    try:
        send_mail('IdentiPy Server notification', 'Search %s was finished' % searchname,
            'identipymail@gmail.com', [username, ])
    except Exception as e:
        logger.error('Could not send email to user %s about run %s:\n%s', username, searchname, e)
    else:
        logger.info('Email notification on search %s sent to %s', searchname, username)
