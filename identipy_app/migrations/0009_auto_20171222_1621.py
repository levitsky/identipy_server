# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-12-22 13:21
from __future__ import unicode_literals

from django.db import migrations
from django.contrib.auth.models import User
import os

def assign_params(apps, schema_editor):
    SearchGroup = apps.get_model('identipy_app', 'SearchGroup')
    ParamsFile = apps.get_model('identipy_app', 'ParamsFile')
    for sg in SearchGroup.objects.all():
        try:
            df = os.path.join('uploads', 'params', str(sg.user.id), sg.groupname + '.cfg')
            params = ParamsFile.objects.get(user=sg.user, docfile=df)
            print 'Matched:', df
        except ParamsFile.DoesNotExist:
            try:
                df = os.path.join('uploads', 'params', str(sg.user.id), sg.groupname).replace(
                    ' ', '_').replace(':', '').split('.')[0]
                params = ParamsFile.objects.get(user=sg.user, docfile__startswith=df)
                print 'Matched beginning:', df
            except ParamsFile.DoesNotExist:
                params = None
                print 'NOT MATCHED:', df
        except Exception:
            print 'User does not exist for SearchGroup:', sg.id, sg.groupname
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