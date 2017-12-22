# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-12-22 13:21
from __future__ import unicode_literals

from django.db import migrations
import os

def assign_params(apps, schema_editor):
    SearchGroup = apps.get_model('identipy_app', 'SearchGroup')
    ParamsFile = apps.get_model('identipy_app', 'ParamsFile')
    for sg in SearchGroup.objects.all():
        try:
            params = ParamsFile.objects.get(user=sg.user,
                docfile=os.path.join('uploads', 'params', str(sg.user.id), sg.groupname + '.cfg'))
        except ParamsFile.DoesNotExist:
            params = None
        sg.parameters = params
        sg.save()


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0008_auto_20171222_1619'),
    ]

    operations = [
            migrations.RunPython(assign_params),
    ]
