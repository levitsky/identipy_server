from models import ParamsFile, Protease
from forms import SearchParametersForm
from django.core.files import File

from django.conf import settings
import os
os.chdir(settings.BASE_DIR)
import sys
import csv
sys.path.insert(0, '../identipy/')
from identipy.utils import CustomRawConfigParser
from forms import SubmitButtonField
from django.utils.safestring import mark_safe
import numpy as np

def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return float(total_size)

class ResultsDetailed():
    def __init__(self, ftype, path_to_csv):
        self.ftype = ftype
        self.order_by_revers = False
        with open(path_to_csv, "r") as cf:
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
        if self.ftype == 'protein' and name == 'dbname':
            return SubmitButtonField(label="", initial="").widget.render3(value)
        elif self.ftype == 'protein' and name == 'description':
            return SubmitButtonField(label="", initial="").widget.render5(value)
        elif self.ftype == 'protein' and name == 'PSMs':
            return SubmitButtonField(label="", initial="").widget.render4('PSMs_link', value, 'show_psms', dbname)
        elif self.ftype == 'protein' and name == 'peptides':
            return SubmitButtonField(label="", initial="").widget.render4('Peptides_link', value, 'show_peptides', dbname)
        elif self.ftype == 'peptide' and name == 'sequence':
            return SubmitButtonField(label="", initial="").widget.render4('PSMs_link', value, 'show_psms', dbname)
        else:
            return value

    def filter_dbname(self, dbname):
        self.dbname = dbname

    def custom_labels(self, whitelist):
        for idx, label in enumerate(self.labels):
            self.whiteind[idx] = label in whitelist

    def change_order(self):
        self.order_by_revers = not self.order_by_revers

    def custom_order(self, order_by_label=False):
        self.change_order()
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

class Menubar():
    def __init__(self, focus, user):
        self.bars = [
            {'id': 'about', 'value': 'about', 'name': 'about'},
            {'id': 'loginform', 'value': u'log\xa0in', 'name': 'loginform'},
            {'id': 'searchpage', 'value': u'Start\xa0search', 'name': 'searchpage'},
            {'id': 'upload', 'value': u'Upload\xa0files', 'name': 'uploadform'},
            {'id': 'get_status', 'value': u'Search\xa0history', 'name': 'getstatus'},
            {'id': 'contacts', 'value': 'contacts', 'name': 'contacts'}
        ]
        self.focus = focus
        self.user = user

    def get_elements(self):
        for bar in self.bars:
            if (self.user and bar.get('id') not in ['about', 'loginform']) or (not self.user and bar.get('id') not in ['searchpage', 'upload', 'get_status']):
                bar['class'] = '"menubar'
                if bar.get('id') == self.focus:
                    # bar['class'] = 'menubar current'
                    bar['class2'] = ' current"'
                else:
                    # bar['class'] = 'menubar'
                    bar['class2'] = '"'
                yield bar

def save_mods(uid, chosenmods, fixed, paramtype=3):
    paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), user=uid)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('ASCII'))
    labels = ','.join([mod.get_label() for mod in chosenmods])
    raw_config.set('modifications', 'fixed' if fixed else 'variable', labels + '|type>string')
    for mod in chosenmods:
        raw_config.set('modifications', mod.label, mod.mass)
    raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))


def save_params_new(sfForms, uid, paramsname=False, paramtype=3, request=False, visible=True):
    paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), user=uid, type=paramtype)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('ASCII'))
    if request:
        sfForms = {}
        for sftype in ['main', 'postsearch']:
            sfForms[sftype] = SearchParametersForm(request.POST, raw_config=raw_config, user=request.user, label_suffix='', sftype=sftype, prefix=sftype)
    for sf in sfForms.values():
        SearchParametersForm_values = {v.name: v.value() for v in sf}
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
    raw_config.set('missed cleavages', 'number of missed cleavages', raw_config.get('search', 'number of missed cleavages'))
    raw_config.set('fragment mass', 'mass accuracy', raw_config.get('search', 'product accuracy'))
    raw_config.set('charges', 'min charge', raw_config.get('search', 'minimum charge'))
    raw_config.set('charges', 'max charge', raw_config.get('search', 'maximum charge'))

    if paramsname:
        fl = open(paramsname + '.cfg', 'w')
        fl.close()
        fl = open(paramsname + '.cfg')
        djangofl = File(fl)
        paramobj = ParamsFile(docfile=djangofl, user=uid, type=paramtype, visible=visible)
        paramobj.save()
        fl.close()
        os.remove(paramsname + '.cfg')
    print paramobj.docfile.name.encode('ASCII')
    raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))
    return paramobj
