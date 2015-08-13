from models import ParamsFile
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
import os
import sys
sys.path.append('../identipy/')
from identipy.utils import CustomRawConfigParser

def save_params(SearchParametersForm_values, uid, paramsname, paramtype=3):
    SearchParametersForm_values = {v.name: v.value() for v in SearchParametersForm_values}
    try:
        paramobj = ParamsFile.objects.get(docfile__endswith='latest_params_%d.cfg' % (paramtype, ), userid=uid)
    except ObjectDoesNotExist:
        print("Either the entry or blog doesn't exist.")
        fl = open('latest_params_%d.cfg' % (paramtype, ))
        djangofl = File(fl)
        paramobj = ParamsFile(docfile = djangofl, userid = uid, type=paramtype)
        paramobj.save()
        fl.close()
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('ASCII'))
    print SearchParametersForm_values.items()
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


    fl = open(paramsname + '.cfg', 'w')
    fl.close()
    fl = open(paramsname + '.cfg')
    djangofl = File(fl)
    paramobj = ParamsFile(docfile = djangofl, userid = uid, type=paramtype)
    paramobj.save()
    fl.close()
    os.remove(paramsname + '.cfg')

    raw_config.write(open(paramobj.docfile.name.encode('ASCII'), 'w'))