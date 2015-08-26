# -*- coding: utf-8 -*-
from django import forms
from multiupload.fields import MultiFileField
from collections import OrderedDict
from models import Protease

from django.utils import html
from django.utils.safestring import mark_safe

class SubmitButtonWidget(forms.Widget):
    def render(self, id, name, value, attrs=None):
        return '<input id="%s" type="submit" class="link" value="%s" name="%s">' % (html.escape(id), html.escape(name), html.escape(value))
    def render2(self, label, help, attrs=None):
        return '<span title="%s">%s</span>' % (html.escape(help), html.escape(label))


class SubmitButtonField(forms.Field):
    def __init__(self, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        kwargs["widget"] = SubmitButtonWidget

        super(SubmitButtonField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return value


sftype_map = {
    'psm count': 'postsearch',
    'psms per protein': 'postsearch',
    'charge states': 'postsearch',
    'potential modifications': 'postsearch',
    'fragment mass tolerance, da': 'postsearch',
    'precursor mass difference, ppm': 'postsearch',
    'isotopes mass difference, da': 'postsearch',
    'missed cleavages': 'postsearch',
    'rt difference, min': 'postsearch'
}

params_map = {
    'enzyme':'enzyme:\t'+SubmitButtonField(label="", initial="").widget.render('enzymelink', 'add custom cleavage rule', 'add_protease'),
    'fixed': SubmitButtonField(label="", initial="").widget.render('modiflink', 'select fixed modifications', 'select_fixed'),
    'variable': SubmitButtonField(label="", initial="").widget.render('modiflink', 'select potential modifications', 'select_potential'),
    'show empty': ('show unmached spectra in results', 'help'),
    'fdr': ('FDR', 'False discovery rate in %'),
    'protfdr': ('protein FDR', 'help'),
    'candidates': ('report number of sequence candidates', 'help'),
    'score': ('search engine score', 'help'),
    'minimum matched': ('minimum number of matched fragments', 'help'),
    'minimum peaks': ('minimum number of fragments in spectra', 'help'),
    'maximum peaks': ('select top n peaks in spectra', 'help'),
    'add decoy': ('generate decoy database on the fly', 'help'),
    'minimum charge': ('minimum precursor charge', 'help'),
    'product accuracy': ('product accuracy, Da', 'help'),
    'psm count': ('post-search validation, PSM count', 'help'),
    'psms per protein': ('post-search validation, PSMs per protein', 'help'),
    'charge states': ('post-search validation, charge states', 'help'),
    'potential modifications': ('post-search validation, potential modifications', 'help'),
    'fragment mass tolerance, da': ('post-search validation, fragment mass tolerance', 'help'),
    'precursor mass difference, ppm': ('post-search validation, precursor mass difference', 'help'),
    'isotopes mass difference, da': ('post-search validation, isotopes mass error', 'help'),
    'missed cleavages': ('post-search validation, missed cleavages', 'help'),
    'rt difference, min': ('post-search validation, RT difference', 'help')
}

def get_label(name):
    if name not in ['enzyme', 'fixed', 'variable']:
        tmplabel, tmphelp = params_map.get(name, [name, ''])
        return SubmitButtonField(label="", initial="").widget.render2(tmplabel, tmphelp)
    else:
        return params_map[name]

class CommonForm(forms.Form):
    commonfiles = MultiFileField(min_num=1, max_num=100, max_file_size=1024*1024*1024*100, label='Upload')

class MultFilesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        relates_to_queryset = kwargs.pop('custom_choices')
        labelname = kwargs.pop('labelname', None)
        multiform = kwargs.pop('multiform', True)
        if not labelname:
            labelname = 'Select files'
        super(MultFilesForm, self).__init__(*args, **kwargs)
        if multiform:
            self.fields['relates_to'] = forms.MultipleChoiceField(label=labelname, choices=relates_to_queryset, widget=forms.CheckboxSelectMultiple, required=False)
        else:
            self.fields['relates_to'] = forms.ChoiceField(label=labelname, choices=relates_to_queryset, widget=forms.RadioSelect, required=False)


class SearchParametersForm(forms.Form):

    def __init__(self, *args, **kwargs):
        raw_config = kwargs.pop('raw_config', 0)
        userid = kwargs.pop('user', None)
        sftype = kwargs.pop('sftype', 'main')
        super(SearchParametersForm, self).__init__(*args, **kwargs)

        def get_allowed_values(settings, sftype):
            for section in settings.sections():
                for param in settings.items(section):
                    if '|' in param[1]:
                        if sftype_map.get(param[0], 'main') == sftype:
                            yield [param[1][::-1].split('|', 1)[0][::-1], ] + [param[0], param[1][::-1].split('|', 1)[-1][::-1]]

        def get_field(fieldtype, label, initial):
            if fieldtype == 'type>float':
                return forms.FloatField(label=label, initial=initial, required=False)
            elif fieldtype == 'type>int':
                return forms.IntegerField(label=label, initial=initial, required=False)
            elif fieldtype == 'type>string':
                return forms.CharField(label=label, initial=initial, required=False, widget=forms.TextInput(attrs=({'readonly': 'readonly'} if label in [get_label('fixed'), get_label('variable')] else {})))
            elif fieldtype == 'type>boolean':
                return forms.BooleanField(label=label, initial=True if int(initial) else False, required=False)
        if raw_config:
            for param in get_allowed_values(raw_config, sftype):
                label = mark_safe(get_label(param[1]))
                if 'class>protease' in param[0]:
                    proteases = Protease.objects.filter(user=userid)
                    if proteases.count():
                        choices = []
                        initial = param[2]
                        for p in proteases.order_by('order_val'):
                            choices.append([p.rule, p.name])
                        initial = choices[[z[1] for z in choices].index(initial)][0]
                    else:
                        initial = 'trypsin'
                        choices = [['[RK]', 'trypsin'], ]
                    self.fields[param[1]] = forms.ChoiceField(
                        label=label,
                        choices=choices[::-1],
                        initial=initial,
                        )
                elif 'type' not in param[0]:
                    self.fields[param[1]] = forms.ChoiceField(
                        label=label,
                        choices=[[x, x] for x in param[0].split(',')],
                        initial=param[2],
                        )
                else:
                    self.fields[param[1]] = get_field(fieldtype=param[0], label=label, initial=param[2])
        key_order = ["use auto optimization",
                    "enzyme",
                    "number of missed cleavages",
                    "precursor accuracy unit",
                    "precursor accuracy left",
                    "precursor accuracy right",
                    "product accuracy",
                    "fdr",
                    "protfdr",
                    "minimum charge",
                    "maximum charge",
                    "add decoy",
                    "decoy method",
                    "decoy prefix",
                    "dynamic range",
                    "peptide minimum length",
                    "peptide maximum length",
                    "peptide minimum mass",
                    "peptide maximum mass",
                    "minimum peaks",
                    "maximum peaks",
                    "product minimum m/z",
                    "maximum fragment charge",
                    "minimum matched",
                    "score",
                    "score threshold",
                    "show empty",
                    "candidates",
                    "model",
                    "psm count",
                    "psms per protein",
                    "charge states",
                    "potential modifications",
                    "fragment mass tolerance, da",
                    "precursor mass difference, ppm",
                    "isotopes mass difference, da",
                    "missed cleavages",
                    "rt difference, min",
                    "fixed",
                    "variable"]

        od = OrderedDict((k, self.fields[k]) for k in key_order if k in self.fields)
        od.update(self.fields)
        self.fields = od

class ContactForm(forms.Form):
    from_email = forms.EmailField(required=True)
    subject = forms.CharField(required=True)
    message = forms.CharField(widget=forms.Textarea)


class AddProteaseForm(forms.Form):
    name = forms.CharField(max_length=50, required=True)
    cleavage_rule = forms.CharField(required=True)


class AddModificationForm(forms.Form):
    name = forms.CharField(max_length=80, required=True)
    label = forms.CharField(max_length=30, required=True)
    mass = forms.FloatField(required=True)
    aminoacids = forms.CharField(max_length=25, required=True)