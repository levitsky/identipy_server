# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-12-21 23:13
from __future__ import unicode_literals

from django.db import migrations, models

def define_runs_img(apps, schema_editor):
    SearchRun = apps.get_model('identipy_app', 'SearchRun')
    ResImageFile = apps.get_model('identipy_app', 'ResImageFile')
    f2r = {}
    for run in SearchRun.objects.all():
        for f in run.resimagefiles.all():
            f2r[f] = run
    for img in ResImageFile.objects.all():
        img.run = f2r.get(img, SearchRun.objects.all().first())
        img.save()


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0005_auto_20171222_0210'),
    ]

    operations = [
            migrations.AddField('ResImageFile', 'run', models.ForeignKey('SearchRun', null=True, on_delete=models.CASCADE), False),
            migrations.RunPython(define_runs_img),
            migrations.AlterField('ResImageFile', 'run', models.ForeignKey('SearchRun', on_delete=models.CASCADE), True),
    ]
