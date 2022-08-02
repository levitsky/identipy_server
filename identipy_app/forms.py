from django import forms
from django.conf import settings
import os
from django_select2 import forms as s2forms
os.chdir(settings.BASE_DIR)

from . import models

import logging
logger = logging.getLogger(__name__)


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


class S2ProteaseWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = ['name__icontains']


class S2ModificationWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = ['name__icontains']


class UserObjectDeletionForm(forms.Form):

    def __init__(self, *args, **kwargs):
        user = models.User.objects.get(pk=kwargs.pop('userid'))
        model = kwargs.pop('model')
        super(UserObjectDeletionForm, self).__init__(*args, **kwargs)
        queryset = model.objects.filter(user=user)
        self.fields['selection'].queryset = queryset

    selection = forms.ModelMultipleChoiceField(None, widget=forms.widgets.CheckboxSelectMultiple)


class BasicSearchParametersForm(forms.ModelForm):
    class Meta:
        model = models.SearchParameters
        fields = ['send_email_notification', 'use_auto_optimization', 'proteases', 'fdr',
            'fixed_modifications', 'variable_modifications']
        widgets = {'proteases': S2ProteaseWidget(attrs={'data-minimum-input-length': 0}),
            'fixed_modifications': S2ModificationWidget(attrs={'data-minimum-input-length': 0}),
            'variable_modifications': S2ModificationWidget(attrs={'data-minimum-input-length': 0})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super(BasicSearchParametersForm, self).__init__(*args, **kwargs)
        self.fields['proteases'].queryset = models.Protease.objects.filter(user=user)
        self.fields['fixed_modifications'].queryset = models.Modification.objects.filter(user=user)
        self.fields['variable_modifications'].queryset = models.Modification.objects.filter(user=user)


class MediumSearchParametersForm(BasicSearchParametersForm):
    class Meta:
        model = BasicSearchParametersForm.Meta.model
        fields = BasicSearchParametersForm.Meta.fields + [
            'add_decoy', 'decoy_prefix', 'number_of_missed_cleavages',
            'precursor_accuracy_unit', 'precursor_accuracy_left', 'precursor_accuracy_right',
            'product_accuracy', 'deisotope', 'precursor_isotope_mass_error',
            'maximum_charge', 'minimum_charge', 'maximum_fragment_charge'
            ]
        widgets = BasicSearchParametersForm.Meta.widgets


class AdvancedSearchParametersForm(MediumSearchParametersForm):
    class Meta:
        model = MediumSearchParametersForm.Meta.model
        fields = MediumSearchParametersForm.Meta.fields + [
            'product_minimum_mz', 'peptide_maximum_length', 'peptide_minimum_length',
            'peptide_maximum_mass', 'peptide_minimum_mass', 'mass_shifts', 'snp',
            'protein_cterm_cleavage', 'protein_nterm_cleavage', 'maximum_variable_mods',
            'decoy_method', 'minimum_peaks', 'maximum_peaks', 'dynamic_range', 'deisotoping_mass_tolerance'
        ]
        widgets = MediumSearchParametersForm.Meta.widgets


_search_parameters_levels = [
    BasicSearchParametersForm, MediumSearchParametersForm, AdvancedSearchParametersForm]


def params_from_post(request):
    if request.method != 'POST':
        raise TypeError('{} request given.'.format(request.method))
    paramtype = request.session.get('paramtype', 3)
    formclass = _search_parameters_levels[paramtype-1]
    form = formclass(request.POST, user=request.user)
    instance = form.save()
    return instance


def search_form_from_request(request, ignore_post=False):
    paramobj = _get_latest_params(request)
    post = request.POST if request.method == 'POST' and not ignore_post else None
    paramtype = request.session.get('paramtype', 3)
    return search_form_for_params(paramobj, post, paramtype)


def search_form_for_params(paramobj, post=None, paramtype=3):
    formclass = _search_parameters_levels[paramtype-1]
    if post:
        return formclass(post, instance=paramobj, user=paramobj.user)
    else:
        return formclass(instance=paramobj, user=paramobj.user)


def _get_latest_params(request):
    return models.User.objects.get(pk=request.user.id).latest_params


class ContactForm(forms.Form):
    subject = forms.CharField(required=True)
    message = forms.CharField(widget=forms.Textarea)


class AddProteaseForm(forms.ModelForm):
    class Meta:
        model = models.Protease
        fields = ('name', 'rule')


class AddModificationForm(forms.Form):
    # class Meta:
    #     model = models.Modification
    #     fields = '__all__'

    name = forms.CharField(max_length=80, required=True)
    label = forms.CharField(max_length=30, required=True)
    mass = forms.CharField(max_length=80, required=True)
    aminoacids = forms.CharField(max_length=25, required=True)


class RenameForm(forms.Form):
    newname = forms.CharField(max_length=80, required=True, label='Rename')
