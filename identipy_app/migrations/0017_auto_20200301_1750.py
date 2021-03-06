# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-03-01 14:50
from __future__ import unicode_literals

from django.db import migrations, models
import identipy_app.models


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0016_auto_20191025_1622'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fastafile',
            name='docfile',
            field=models.FileField(max_length=200, upload_to=identipy_app.models.upload_to_fasta),
        ),
        migrations.AlterField(
            model_name='paramsfile',
            name='docfile',
            field=models.FileField(max_length=200, upload_to=identipy_app.models.upload_to_params),
        ),
        migrations.AlterField(
            model_name='pepxmlfile',
            name='docfile',
            field=models.FileField(max_length=200, storage=identipy_app.models.OverwriteStorage(), upload_to=identipy_app.models.upload_to_pepxml),
        ),
        migrations.AlterField(
            model_name='rawfile',
            name='docfile',
            field=models.FileField(max_length=200, upload_to=identipy_app.models.upload_to_raw),
        ),
        migrations.AlterField(
            model_name='rescsv',
            name='docfile',
            field=models.FileField(max_length=200, storage=identipy_app.models.OverwriteStorage(), upload_to=identipy_app.models.upload_to_pepxml),
        ),
        migrations.AlterField(
            model_name='resimagefile',
            name='docfile',
            field=models.ImageField(max_length=200, storage=identipy_app.models.OverwriteStorage(), upload_to=identipy_app.models.upload_to_pepxml),
        ),
        migrations.AlterField(
            model_name='spectrafile',
            name='docfile',
            field=models.FileField(max_length=200, upload_to=identipy_app.models.upload_to_spectra),
        ),
    ]
