# -*- coding: utf-8 -*-
from django import forms
from multiupload.fields import MultiFileField


class CommonForm(forms.Form):
    commonfiles = MultiFileField(min_num=1, max_num=100, max_file_size=1024*1024*1024*100, label='Upload files')

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
            labelname = 'Choose files'
        super(MultFilesForm, self).__init__(*args, **kwargs)
        if multiform:
            self.fields['relates_to'] = forms.MultipleChoiceField(label=labelname, choices=relates_to_queryset, widget=forms.CheckboxSelectMultiple, required=False)
        else:
            self.fields['relates_to'] = forms.ChoiceField(label=labelname, choices=relates_to_queryset, widget=forms.Select, required=False)