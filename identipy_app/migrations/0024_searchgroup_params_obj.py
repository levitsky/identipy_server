# Generated by Django 4.0.4 on 2022-05-25 13:56

from django.db import migrations, models
import django.db.models.deletion
import configparser
import re
import string

_modchars = set(string.ascii_lowercase + string.digits + string.punctuation) - set('[]-')
def custom_split_label(mod):
    j = 0
    while mod[j] in _modchars:
        j += 1
    if j == 0:
        return mod[1:], '-', ']'
    if len(mod[j:]) > 1 and '[' in mod:
        return mod[:j], mod[j:].replace('[', ''), '['
    elif len(mod[j:]) > 1 and ']' in mod:
        return mod[:j], mod[j:].replace(']', ''), ']'
    elif len(mod[j:]) == 1:
        if mod.startswith('-'):
            return mod[:j], '-', ']'
        elif mod.endswith('-'):
            return mod[:j], '-', '['
        else:
            return mod[:j], mod[j:], ''

class CustomRawConfigParser(configparser.RawConfigParser, object):
    def get(self, section, option, **kwargs):
        val = super(CustomRawConfigParser, self).get(section, option)
        if isinstance(val, str):
            if section == 'search' and option == 'enzyme':
                return val.split('|class')[0]
            return val[::-1].split('|', 1)[-1][::-1]
        return val

    def get_choices(self, section, option):
        val = super(CustomRawConfigParser, self).get(section, option)
        if isinstance(val, str) and len(val.split('|')) > 1:
            return val[::-1].split('|', 1)[0][::-1]
        else:
            return ''

    def copy(self):
        new_config = CustomRawConfigParser()
        for section in self.sections():
            new_config.add_section(section)
            for name, value in self.items(section):
                new_config.set(section, name, value)
        return new_config


field_types = {
        'BooleanField': lambda c, s, o: c.getboolean(s, o),
        'FloatField': lambda c, s, o: c.getfloat(s, o),
        'PositiveSmallIntegerField': lambda c, s, o: c.getint(s, o),
    }


def get_field_converter(apps, field, user):
    Protease = apps.get_model('identipy_app', 'Protease')
    Modification = apps.get_model('identipy_app', 'Modification')
    SearchParameters = apps.get_model('identipy_app', 'SearchParameters')
    if field == 'proteases':
        def f(c, s, o):
            proteases = []
            for x in c.get(s, o).split(','):
                try:
                    p = Protease.objects.get(user=user, rule=x)
                except Protease.DoesNotExist:
                    try:
                        p = Protease.objects.get(user=user, name=x)
                    except Protease.DoesNotExist:
                        p = Protease(user=user, rule=x, name=x, order_val=Protease.objects.order_by('order_val').last().order_val + 1)
                        p.save()
                        print('Created protease for user {0.user.id}: rule="{0.rule}"'.format(p))
                proteases.append(p)
            return proteases
        return f
    if field in {'fixed_modifications', 'variable_modifications'}:
        def f(c, s, o):
            mods = []
            for x in re.split(r',\s*', c.get(s, o)):
                if x:
                    mod, aa, term = custom_split_label(x)
                    if aa == '-':
                        aa = term
                    try:
                        modification = Modification.objects.get(user=user, aminoacid=term+aa, label=mod)
                    except Modification.DoesNotExist:
                        modification = Modification(user=user, aminoacid=term+aa, label=mod, mass=c.getfloat(s, mod),
                            name=mod+term+aa)
                        print('Created missing modification for user {0.user.id}: {0.label} on {0.aminoacid}, mass {0.mass}'.format(modification))
                        modification.save()
                    mods.append(modification)
            return mods
        return f
    choices = SearchParameters._meta.get_field(field).choices
    if choices:
        def f(c, s, o):
            value = c.get(s, o)
            for raw, label in choices:
                if value == label:
                    return raw
        return f
    field_type = SearchParameters._meta.get_field(field).get_internal_type()
    return field_types.get(field_type, lambda c, s, o: c.get(s, o))

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


def read_file(apps, sg):
    SearchParameters = apps.get_model('identipy_app', 'SearchParameters')
    if not sg.parameters:
        print('WARNING: SearchGroup {} has no parameters.'.format(sg.id))
        return None
    fname = sg.parameters.docfile.name
    user = sg.user
    config = CustomRawConfigParser(allow_no_value=True, inline_comment_prefixes=(';', '#'))
    print('Reading: ', fname)
    config.read(fname)
    data = {}
    for (field, (section, option)) in field_names:
        try:
            data[field] = get_field_converter(apps, field, user)(config, section, option)
        except (configparser.NoOptionError, configparser.NoSectionError, ValueError) as e:
            print('WARNING: Could not set field {}: {}'.format(field, e))
    data['user'] = user
    fmods = data.pop('fixed_modifications')
    vmods = data.pop('variable_modifications')
    proteases = data.pop('proteases')
    instance = SearchParameters(**data)
    instance.save()
    instance.fixed_modifications.set(fmods)
    instance.variable_modifications.set(vmods)
    instance.proteases.set(proteases)
    print('Created a SearchParameters object {} for SearchGroup {}'.format(instance.id, sg.id))
    return instance


def create_params(apps, schema_editor):
    SearchGroup = apps.get_model('identipy_app', 'SearchGroup')
    for sg in SearchGroup.objects.all():
        params = read_file(apps, sg)
        sg.params_obj = params
        sg.save()

def undo_create_params(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0023_alter_pepxmlfile_run_alter_rescsv_run_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchgroup',
            name='params_obj',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='identipy_app.searchparameters'),
        ),
        migrations.RunPython(create_params, undo_create_params),
    ]