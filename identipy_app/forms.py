# -*- coding: utf-8 -*-
from django import forms
from multiupload.fields import MultiFileField
from collections import OrderedDict

from django.urls import reverse
from django.utils import html
from django.utils.safestring import mark_safe

from django.conf import settings
import os
os.chdir(settings.BASE_DIR)

from pyteomics import parser

import models

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

    def render6(self, dbname, show_type, value):
        return '<a class="td2" class="link" href="%s?dbname=%s&show_type=%s">%s</a>' % (reverse("identipy_app:show"), dbname, show_type, value)


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
    'product accuracy': ('product accuracy, Da', ''),
    'psm count': ('PSM count', ''),
    'psms per protein': ('PSMs per protein', ''),
    'charge states': ('charge states', ''),
    'potential modifications': ('potential modifications', ''),
    'fragment mass tolerance, da': ('fragment mass tolerance', ''),
    'precursor mass difference, ppm': ('precursor mass difference', ''),
    'isotopes mass difference, da': ('isotopes mass error', ''),
    'missed cleavages': ('missed cleavages', ''),
    'rt difference, min': ('RT difference', ''),
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
    else:
        return params_map[name]


class CommonForm(forms.Form):
    commonfiles = MultiFileField(
        min_num=1, max_num=100, max_file_size=1024 * 1024 * 1024 * 100, label='Upload')


class MultFilesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('custom_choices')
        labelname = kwargs.pop('labelname', 'Select files')
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
        raw_config = kwargs.pop('raw_config', 0)
        userid = kwargs.pop('user', None)
        self.sftype = kwargs.pop('sftype', 'main')
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
                return forms.CharField(label=label, initial=initial, required=False,
                                       widget=forms.TextInput(attrs=(
                                           {'readonly': 'readonly'} if label in [get_label('fixed'), get_label('variable')] else {})))
            elif fieldtype == 'type>boolean':
                return forms.BooleanField(label=label, initial=True if int(initial) else False, required=False)

        if raw_config:
            for param in get_allowed_values(raw_config, self.sftype):
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
                     "fdr_type",
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

        od = OrderedDict((k, self.fields[k])
                         for k in key_order if k in self.fields)
        od.update(self.fields)
        self.fields = od

#class SearchParamsFormBase(forms.Form):
#    _key_order = ["email", "optimization", "enzyme", "numer_of_missed_cleavages",
#            "precursor_accuracy_unit", "precursor_accuracy_left", "precursor_accuracy_right",
#            "precursor_isotope_mass_error", "product_accuracy", "fdr", "fdr_type",
#            "minimum_charge", "maximum_charge", "add_decoy", "decoy_method", "decoy_prefix",
#            "dynamic_range", "peptide_minimum_length", "peptide_maximum_length",
#            "peptide_minimum_mass", "peptide_maximum_mass", "minimum_peaks", "maximum_peaks",
#            "product_minimum_m/z", "maximum_fragment_charge", "minimum_matched", "score", "score_threshold",
##_          "show_empty", "candidates",
#            "model", "psm_count", "psms_per_protein", "charge_states", "potential_modifications",
#            "fragment_mass_tolerance", "precursor_mass_difference", "isotopes_mass_difference",
#            "missed_cleavages", "rt_difference", "fixed", "variable"]
#    
#    def __init__(self, *args, **kwargs):
#        self.user = kwargs.pop('user', None)
#        kwargs.setdefault('field_order', SearchParamsFormBase._key_order)
#        super(SearchParamsFormBase, self).__init__(*args, **kwargs)
#
#class SearchParamsForm1(SearchParamsFormBase):
#    _labels = {'enzyme': mark_safe('enzyme:\t<input id="enzymelink" type="submit" class="link"'
#        ' value="add custom cleavage rule" name="submit_action">'),
#        'fixed': mark_safe('<input type="submit" class="link modiflink" value="select fixed modifications" name="submit_action">'),
#        'variable': mark_safe('<input type="submit" class="link modiflink" value="select potential modifications" name="submit_action">')}
#
#    def __init__(self, *args, **kwargs):
#        super(SearchParamsForm1, self).__init__(*args, **kwargs)
#        if 'enzyme' in self.fields:
#            e = self.fields['enzyme']
#            proteases = models.Protease.objects.filter(user=self.user).order_by('order_val')
#            choices = [(p.rule, p.name) for p in proteases]
#            if not choices: choices.append((parser.expasy_rules['trypsin'], 'trypsin'))
#            self.fields['enzyme'] = forms.ChoiceField(label=e.label, label_suffix=e.label_suffix,
#                    choices=choices, required=e.required, initial=choices[0])
#
#    email = forms.BooleanField(label='send email notification', required=False)
##   optimization = forms.BooleanField(label='use auto optimization', required=False)
#    enzyme = forms.ChoiceField(label=_labels['enzyme'], label_suffix='',
#        choices=[], required=True)
#    precursor_isotope_mass_error = forms.IntegerField(min_value=0, initial=0) 
#    fdr = forms.FloatField(label='FDR', initial=1.0)
#    fdr_type = forms.ChoiceField(
#            choices = [('psm', 'psm'), ('peptide', 'peptide'), ('protein', 'protein')],
#            label = 'FDR type')
#    _modwidget = forms.TextInput(attrs={'readonly': 'readonly'})
#    fixed = forms.CharField(widget=_modwidget, required=False,
#            label=_labels['fixed'])
#    variable = forms.CharField(widget=_modwidget, required=False,
#            label=_labels['variable'])
#
#class PostSearchForm(forms.Form):
#    pass #TODO

from identipy.utils import CustomRawConfigParser
#def search_params_form(request):
#    paramtype = request.session['paramtype']
#    assert 1 <= paramtype <= 3, "Invalid paramtype"
#    mainformclass = SearchParametersForm
#    postform = None
#    if request.method == 'POST':
#        mainform = mainformclass(request.POST, user=request.user.id)
#        if paramtype == 3:
##           postform = PostSearchForm(request.POST)
#            postform = SearchParametersForm(request.POST, sftype='postsearch')
#    else:
#        mainform = mainformclass(user=request.user.id)
#        if paramtype == 3:
##           postform = PostSearchForm()
#            postform = SearchParametersForm(sftype='postsearch')
#    return {'main': mainform, 'postsearch': postform}

def search_forms_from_request(request, ignore_post=False):
#   import models
    sForms = {}
    kwargs = _kwargs_for_search_form(request)
    for sftype in ['main', 'postsearch']:
        kwargs.update(sftype=sftype, prefix=sftype)
        if request.method == 'POST' and not ignore_post:
            sForms[sftype] = SearchParametersForm(request.POST, **kwargs)
        else:
            sForms[sftype] = SearchParametersForm(**kwargs)
    return sForms

def _kwargs_for_search_form(request):
    paramobj = models.ParamsFile.objects.get(docfile__endswith='latest_params_{}.cfg'.format(request.session.setdefault('paramtype', 3)),
            user=request.user.id, type=request.session['paramtype'])
    raw_config = CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(paramobj.docfile.name.encode('utf-8'))
    kwargs = dict(raw_config=raw_config, user=request.user, label_suffix='')
    return kwargs

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

