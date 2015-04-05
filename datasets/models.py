# -*- coding: utf-8 -*-
from django.db import models
from django.core.files.storage import default_storage
import os


def my_upload_function(instance, filename):
    allowed_extensions = {'.raw', '.baf', '.yep', '.mgf', '.mzml', '.mzxml', '.fasta'}
    fext = os.path.splitext(filename)[-1]
    if fext in allowed_extensions:
        upfolder = fext[1:]
    else:
        upfolder = 'other'
    return os.path.join('uploads', upfolder, filename)


class Document(models.Model):
    docfile = models.FileField(upload_to=my_upload_function)

    def __unicode__(self):
        return unicode(docfile.name)

    def format(self):
        return os.path.splitext(self.docfile)[-1][1:]

    def delete(self):
        super(Document, self).delete()
        default_storage.delete(self.docfile.name)

    def name(self):
        return os.path.split(self.docfile.name)[-1]
