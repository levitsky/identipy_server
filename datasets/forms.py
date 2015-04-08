# -*- coding: utf-8 -*-
from django import forms


class DocumentForm(forms.Form):
    docfile = forms.FileField(
        label='Select a file'
    )


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
        # try:
        #     labelname = 'Choose %s files' % (kwargs.pop('fextention'), )
        # except:
        labelname = 'Choose files'
        super(MultFilesForm, self).__init__(*args, **kwargs)
        self.fields['relates_to'] = forms.MultipleChoiceField(label=labelname, choices=relates_to_queryset, widget=forms.CheckboxSelectMultiple, required=False)