# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-01-02 17:47
from __future__ import unicode_literals

from django.db import migrations
from django.conf import settings
import os

def rename_dirs(apps, schema_editor):
    SearchGroup = apps.get_model('identipy_app', 'SearchGroup')
    base = settings.BASE_DIR
    for sg in SearchGroup.objects.all():
        target = os.path.join(base, 'results', str(sg.user.id), str(sg.id))
#       if os.path.exists(target):
#           raise OSError('Target exists: ' + target)
        source = os.path.join(base, 'results', str(sg.user.id), sg.groupname)
#       if not os.path.exists(source):
#           raise OSError('Source does not exist: ' + source)
#       print 'Renaming {} to {}'.format(source, target)
        try:
            os.rename(source, target)
        except OSError as e:
            print('Could not rename {} to {}: {}'.format(source, target, e))

    ResImageFile = apps.get_model('identipy_app', 'ResImageFile')
    ResCSV = apps.get_model('identipy_app', 'ResCSV')
    PepXMLFile = apps.get_model('identipy_app', 'PepXMLFile')
    for Model in [ResImageFile, ResCSV, PepXMLFile]:
        for obj in Model.objects.all():
            dir, f = os.path.split(obj.docfile.name)
            prefix, name = os.path.split(dir)
            newpath = os.path.join(prefix, str(obj.run.searchgroup.id), f)
#           print obj.docfile.name, '->', newpath
            obj.docfile.name = newpath
            obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0010_auto_20171230_1714'),
    ]

    operations = [
            migrations.RunPython(rename_dirs)
    ]
