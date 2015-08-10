# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datasets.models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FastaFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.FileField(upload_to=datasets.models.upload_to_fasta)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ParamsFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.FileField(upload_to=datasets.models.upload_to_params)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PepXMLFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.FileField(storage=datasets.models.OverwriteStorage(), upload_to=datasets.models.upload_to_pepxml)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RawFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.FileField(upload_to=datasets.models.upload_to_raw)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ResCSV',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.FileField(storage=datasets.models.OverwriteStorage(), upload_to=datasets.models.upload_to_pepxml)),
                ('ftype', models.CharField(max_length=10)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ResImageFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.ImageField(storage=datasets.models.OverwriteStorage(), upload_to=datasets.models.upload_to_pepxml)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SearchGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('groupname', models.CharField(default=b'test', max_length=80)),
                ('status', models.CharField(default=b'No info', max_length=80)),
                ('fasta', models.ManyToManyField(to='datasets.FastaFile')),
                ('parameters', models.ManyToManyField(to='datasets.ParamsFile')),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SearchRun',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('runname', models.CharField(max_length=80)),
                ('numMSMS', models.BigIntegerField(default=0)),
                ('totalPSMs', models.BigIntegerField(default=0)),
                ('fdr_psms', models.FloatField(default=0.0)),
                ('fdr_prots', models.FloatField(default=-1.0)),
                ('numPSMs', models.BigIntegerField(default=0)),
                ('numPeptides', models.BigIntegerField(default=0)),
                ('numProteins', models.BigIntegerField(default=0)),
                ('union', models.BooleanField(default=False)),
                ('csvfiles', models.ManyToManyField(to='datasets.ResCSV')),
                ('fasta', models.ManyToManyField(to='datasets.FastaFile')),
                ('parameters', models.ManyToManyField(to='datasets.ParamsFile')),
                ('pepxmlfiles', models.ManyToManyField(to='datasets.PepXMLFile')),
                ('resimagefiles', models.ManyToManyField(to='datasets.ResImageFile')),
                ('searchgroup_parent', models.ForeignKey(to='datasets.SearchGroup')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SpectraFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('docfile', models.FileField(upload_to=datasets.models.upload_to_spectra)),
                ('userid', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='searchrun',
            name='spectra',
            field=models.ManyToManyField(to='datasets.SpectraFile'),
        ),
        migrations.AddField(
            model_name='searchrun',
            name='userid',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
    ]
