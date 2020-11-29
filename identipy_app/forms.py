# -*- coding: utf-8 -*-
from django import forms
from collections import OrderedDict
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils import html
import os
os.chdir(settings.BASE_DIR)

from pyteomics import parser
from . import models
from identipy.utils import CustomRawConfigParser


class SubmitButtonWidget(forms.Widget):
    def render(self, id, name, value, attrs=None):
        return '<input id="%s" type="submit" class="link" value="%s" name="%s">' % (html.escape(id), html.escape(name), html.escape(value))

    def render2(self, label, help, attrs=None):
        if html.escape(help):
            return '<span title="%s" style="cursor:help">%s</span>' % (html.escape(help), html.escape(label))
        else:
            return '<span title="" >%s</span>' % (html.escape(label))

    def render3(self, name):
        try:
            return '<a target="_blank" href="http://www.uniprot.org/uniprot/%s">%s</a>' % (html.escape(name).split('|')[1], html.escape(name))
        except:
            return html.escape(name)
        # return '<a target="_blank"
        # href="http://www.uniprot.org/uniprot/%s">%s</a>' % (,
        # html.escape(name))

    def render5(self, name):
        return '<a target="_blank" href="http://www.ncbi.nlm.nih.gov/pubmed/?term=%s">%s</a>' % (html.escape(name.split('OS=')[0]), html.escape(name))

    def render6(self, dbname, show_type, runid, value):
        return '<a class="td2" class="link" href="%s?dbname=%s&show_type=%s&runid=%s">%s</a>' % (reverse("identipy_app:show"), dbname, show_type, runid, value)


class SubmitButtonField(forms.Field):
    def __init__(self, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        kwargs["widget"] = SubmitButtonWidget

        super(SubmitButtonField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return value


params_map = {
    'enzyme': SubmitButtonField(label="", initial="").widget.render(
        'enzymelink', 'enzyme', 'submit_action'),
    'fixed': SubmitButtonField(label="", initial="").widget.render('modiflink', 'select fixed modifications', 'submit_action'),
    'variable': SubmitButtonField(label="", initial="").widget.render('modiflink', 'select potential modifications', 'submit_action'),
    'show empty': ('show unmached spectra in results', ''),
    'fdr': ('FDR', 'false discovery rate in %'),
    'fdr_type': ('FDR type', ''),
    'candidates': ('report number of sequence candidates', ''),
    'score': ('use scoring function', ''),
    'minimum matched': ('matched fragments, min', 'minimum number of matched fragments'),
    'minimum peaks': ('fragments in spectra, min', 'minimum number of fragments in spectra'),
    'maximum peaks': ('fragments in spectra, max', 'select top n peaks in spectra'),
    'add decoy': ('generate decoy db', 'generate decoy database on the fly'),
    'minimum charge': ('minimum charge', 'minimum  precursor charge state'),
    'maximum charge': ('maximum charge', 'maximum  precursor charge state'),
    'precursor isotope mass error': ('precursor isotope mass error', "When the value for this parameter is not 0, "
                                     "the parent ion mass tolerance is expanded by opening up multiple tolerance windows "
                                     "centered on the first N 13C isotope peaks for a peptide. "
                                     "This behavior is necessary to compensate for the tendency of automated "
                                     "peak finding software to return the most intense peak from a cluster of isotopes, "
                                     "rather than the all-12C peak."),
    'shifts': ('peptide mass shift', 'example: 0, 16.000, 23.000, 12')
}


def get_label(name):
    if name not in {'enzyme', 'fixed', 'variable'}:
        tmplabel, tmphelp = params_map.get(name, [name, ''])
        return SubmitButtonField(label="", initial="").widget.render2(tmplabel, tmphelp)
    return params_map[name]


class CommonForm(forms.Form):
    commonfiles = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}),
        label='Upload')


class LocalImportForm(forms.Form):
    filePath = forms.CharField(max_length=120)
    link = forms.BooleanField(required=False)


class MultFilesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('custom_choices')
        labelname = kwargs.pop('labelname', '')
        multiform = kwargs.pop('multiform', True)
        super(MultFilesForm, self).__init__(*args, **kwargs)
        if multiform:
            Widget = forms.CheckboxSelectMultiple
            Field = forms.MultipleChoiceField
        else:
            Widget = forms.RadioSelect
            Field = forms.ChoiceField
        self.fields['choices'] = Field(label=labelname, choices=choices, widget=Widget, required=False)


class SearchParametersForm(forms.Form):

    def __init__(self, *args, **kwargs):
        raw_config = kwargs.pop('raw_config', None)
        userid = kwargs.pop('user', None)
        self.sftype = kwargs.pop('sftype', 'main')
        super(SearchParametersForm, self).__init__(*args, **kwargs)

        def get_values(settings):
            for section in settings.sections():
                for param in settings.items(section):
                    if '|' in param[1]:
                        yield [param[1][::-1].split('|', 1)[0][::-1], ] + [param[0], param[1][::-1].split('|', 1)[-1][::-1]]

        def get_field(fieldtype, label, initial):
            if fieldtype == 'type>float':
                return forms.FloatField(label=label, initial=initial, required=False,
                    widget=forms.NumberInput(attrs={'step': 0.01 if 'product accuracy, Da' in label else 1}))
            elif fieldtype == 'type>int':
                return forms.IntegerField(label=label, initial=initial, required=False)
            elif fieldtype == 'type>string':
                return forms.CharField(label=label, initial=initial, required=False,
                                       widget=forms.TextInput(attrs=(
                                           {'readonly': 'readonly'} if label in [get_label('fixed'), get_label('variable')] else {})))
            elif fieldtype == 'type>boolean':
                return forms.BooleanField(label=label, initial=True if int(initial) else False, required=False)

        if raw_config:
            for param in get_values(raw_config):
                label = mark_safe(get_label(param[1]))
                if 'class>protease' in param[0]:
                    proteases = models.Protease.objects.filter(user=userid)
                    if not proteases.count():
                        protease_object = models.Protease(name='trypsin', rule=parser.expasy_rules[
                                                   'trypsin'], order_val=1, user=userid)
                        protease_object.save()
                    choices = []
                    initial = param[2]
                    for p in proteases.order_by('order_val'):
                        choices.append([p.rule, p.name])
                    try:
                        initial = choices[[z[1] for z in choices].index(initial)][0]
                    except:
                        initial = choices[0][0]
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
                    self.fields[param[1]] = get_field(
                        fieldtype=param[0], label=label, initial=param[2])

        key_order = ["send email notification",
                     "use auto optimization",
                     "enzyme",
                     "number of missed cleavages",
                     "precursor accuracy unit",
                     "precursor accuracy left",
                     "precursor accuracy right",
                     "precursor isotope mass error",
                     "product accuracy",
                     "fdr",
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
                     "fixed",
                     "variable"]

        od = OrderedDict((k, self.fields[k])
                         for k in key_order if k in self.fields)
        od.update(self.fields)
        self.fields = od


def search_forms_from_request(request, ignore_post=False):
    paramobj = _get_latest_params(request)
    post = request.POST if request.method == 'POST' and not ignore_post else None
    paramtype = request.session.get('paramtype', 3)
    return search_form_for_params(paramobj, post, paramtype)


def search_form_for_params(paramobj, post=None, paramtype=3):
    sForms = {}
    kwargs = _sform_kwargs_from_obj(paramobj)
    sftype = 'main'
    kwargs.update(sftype=sftype, prefix=sftype)
    if post:
        sForms[sftype] = SearchParametersForm(post, **kwargs)
    else:
        sForms[sftype] = SearchParametersForm(**kwargs)
    return sForms


def _get_latest_params(request):
    return models.ParamsFile.objects.get(
        docfile__endswith='latest_params_{}.cfg'.format(request.session.setdefault('paramtype', 3)),
        user=request.user.id)


def _sform_kwargs_from_obj(paramobj):
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name)
    kwargs = dict(raw_config=raw_config, user=paramobj.user, label_suffix='')
    return kwargs


def _kwargs_for_search_form(request):
    paramobj = _get_latest_params(request)
    return _sform_kwargs_from_obj(paramobj)


class ContactForm(forms.Form):
    subject = forms.CharField(required=True)
    message = forms.CharField(widget=forms.Textarea)


class AddProteaseForm(forms.Form):
    name = forms.CharField(max_length=50, required=True)
    cleavage_rule = forms.CharField(required=True)


class AddModificationForm(forms.Form):
    name = forms.CharField(max_length=80, required=True)
    label = forms.CharField(max_length=30, required=True)
    mass = forms.CharField(max_length=80, required=True)
    aminoacids = forms.CharField(max_length=25, required=True)


class RenameForm(forms.Form):
    newname = forms.CharField(max_length=80, required=True, label='Rename')
