# -*- coding: utf-8 -*-
# Generated by Django 1.11.25 on 2019-10-25 13:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0015_auto_20190719_2316'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resimagefile',
            name='imgtype',
            field=models.CharField(choices=[(b'S', b'PSM'), (b'P', b'Peptide'), (b'R', b'Protein'), (b'O', b'Feature')], default=b'O', max_length=1),
        ),
        migrations.AlterField(
            model_name='searchrun',
            name='status',
            field=models.CharField(choices=[(b'W', b'Waiting'), (b'R', b'Running'), (b'V', b'Postsearch processing'), (b'F', b'Finished'), (b'D', b'Dead'), (b'E', b'Error')], default=b'D', max_length=1),
        ),
    ]