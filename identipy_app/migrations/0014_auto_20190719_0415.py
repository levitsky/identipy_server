# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-19 01:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0013_auto_20190717_1921'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searchgroup',
            name='fdr_type',
        ),
        migrations.AddField(
            model_name='rescsv',
            name='filtered',
            field=models.BooleanField(default=True),
        ),
    ]
