from models import ParamsFile, Protease
from forms import SearchParametersForm
from django.core.files import File
import os
import sys
sys.path.append('../identipy/')
from identipy.utils import CustomRawConfigParser

def save_mods(uid, chosenmods, fixed, paramtype=3):
    paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), user=uid)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('ASCII'))
    labels = ','.join([mod.label + mod.aminoacid for mod in chosenmods])
    raw_config.set('modifications', 'fixed' if fixed else 'variable', labels + '|type>string')
    for mod in chosenmods:
        raw_config.set('modifications', mod.label, mod.mass)
    raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))


def save_params_new(sfForms, uid, paramsname=False, paramtype=3, request=False):
    paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), user=uid, type=paramtype)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('ASCII'))
    if request:
        sfForms = {}
        for sftype in ['main', 'postsearch']:
            sfForms[sftype] = SearchParametersForm(raw_config=raw_config, user=request.user, label_suffix='', sftype=sftype, prefix=sftype)
        # SearchParametersForm_values = SearchParametersForm(request.POST, raw_config = raw_config, user=request.user, label_suffix='')
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
    protease = Protease.objects.get(user=uid, rule=enz)
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
        paramobj = ParamsFile(docfile = djangofl, user = uid, type=paramtype)
        paramobj.save()
        fl.close()
        os.remove(paramsname + '.cfg')
    print paramobj.docfile.name.encode('ASCII')
    raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))
    return paramobj

def save_params(SearchParametersForm_values, uid, paramsname=False, paramtype=3, request=False):
    paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), user=uid, type=paramtype)
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('ASCII'))
    if request:
        SearchParametersForm_values = SearchParametersForm(request.POST, raw_config = raw_config, user=request.user, label_suffix='')
    SearchParametersForm_values = {v.name: v.value() for v in SearchParametersForm_values}
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
    protease = Protease.objects.get(user=uid, rule=enz)
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
        paramobj = ParamsFile(docfile = djangofl, user = uid, type=paramtype)
        paramobj.save()
        fl.close()
        os.remove(paramsname + '.cfg')
    print paramobj.docfile.name.encode('ASCII')
    raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))
    return paramobj
