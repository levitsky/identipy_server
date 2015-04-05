# -*- coding: utf-8 -*-
from django.db import models
import os


def my_upload_function(instance, filename):
    allowed_extensions = set(('.raw', '.baf', '.yep', '.mgf', '.mzml', '.mzxml', '.fasta'))
    fext = os.path.splitext(filename)[-1]
    if fext in allowed_extensions:
        upfolder = fext[1:]
    else:
        upfolder = 'unknown'
    return os.path.join('%s/%s' % (upfolder, filename))


class Document(models.Model):
    docfile = models.FileField(upload_to=my_upload_function)

    def __unicode__(self):
        return docfile

    def format(self):
        return os.path.splitext(self.docfile)[-1]
