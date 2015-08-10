# -*- coding: utf-8 -*-
from django import forms
from multiupload.fields import MultiFileField
from pyteomics import biolccc
from collections import OrderedDict

class CommonForm(forms.Form):
    commonfiles = MultiFileField(min_num=1, max_num=100, max_file_size=1024*1024*1024*100, label='Upload')

class MultFilesForm(forms.Form):
    # OPTIONS = (
    #         ("AUT", "Australia"),
    #         ("DEU", "Germany"),
    #         )
    # Multfiles = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
    #                                      choices=OPTIONS)

    # def __init__(self, custom_choices=None, *args, **kwargs):
    #     super(MultFilesForm, self).__init__(*args, **kwargs)
    #     if custom_choices:
    #         self.fields['field'].choices = custom_choices

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
            self.fields['relates_to'] = forms.ChoiceField(label=labelname, choices=relates_to_queryset, widget=forms.Select, required=False)

class Survey(forms.Form):
    name = forms.CharField(max_length=20)
    age = forms.IntegerField()




class SearchParametersForm(forms.Form):

    def __init__(self, *args, **kwargs):
        raw_config = kwargs.pop('raw_config', 0)
        super(SearchParametersForm, self).__init__(*args, **kwargs)

        def get_allowed_values(settings):
            for section in settings.sections():
                for param in settings.items(section):
                    if '|' in param[1]:
                        yield [param[1].split('|')[1], ] + [param[0], param[1].split('|')[0]]

        def get_field(fieldtype, label, initial):
            if fieldtype == 'type>float':
                return forms.FloatField(label=label, initial=initial)
            elif fieldtype == 'type>int':
                return forms.IntegerField(label=label, initial=initial)
            elif fieldtype == 'type>string':
                return forms.CharField(label=label, initial=initial)
            elif fieldtype == 'type>boolean':
                return forms.BooleanField(label=label, initial=initial, required=False)

        if raw_config:
            print 'HERE2Q'
            for param in get_allowed_values(raw_config):
                if 'type' not in param[0]:
                    self.fields[param[1]] = forms.ChoiceField(
                        label=param[1],
                        choices=[[x, x] for x in param[0].split(',')],
                        initial=param[0].split(',')[0],
                        )
                else:
                    self.fields[param[1]] = get_field(fieldtype=param[0], label=param[1], initial=param[2])
        key_order = ["precursor accuracy unit",
                    "precursor accuracy left",
                    "precursor accuracy right",
                    "product accuracy",
                    "fdr",
                    "protfdr",
                    "enzyme",
                    "number of missed cleavages",
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
                    "rt difference, min"]

        od = OrderedDict((k, self.fields[k]) for k in key_order if k in self.fields)
        od.update(self.fields)
        self.fields = od
        # self.fields.keyOrder = [
        #     'minimum peaks',
        #     'maximum peaks']

    # def add_params(self, raw_config):
    #     def get_allowed_values(settings):
    #         for section in settings.sections():
    #             for param in settings.items(section):
    #                 if '|' in param[1]:
    #                     yield [param[1].split('|')[1], ] + [param[0], param[1].split('|')[0]]
    #
    #     def get_field(fieldtype, label, initial):
    #         if fieldtype == 'type>float':
    #             return forms.FloatField(label=label, initial=initial)
    #         elif fieldtype == 'type>int':
    #             return forms.IntegerField(label=label, initial=initial)
    #         elif fieldtype == 'type>string':
    #             return forms.CharField(label=label, initial=initial)
    #
    #     for param in get_allowed_values(raw_config):
    #         if 'type' not in param[0]:
    #             self.fields[param[1]] = forms.ChoiceField(
    #                 label=param[1],
    #                 choices=[[x, x] for x in param[0].split(',')],
    #                 initial=param[0].split(',')[0],
    #                 )
    #         else:
    #             self.fields[param[1]] = get_field(fieldtype=param[0], label=param[1], initial=param[2])