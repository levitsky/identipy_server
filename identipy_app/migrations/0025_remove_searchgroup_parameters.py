# Generated by Django 4.0.4 on 2022-06-29 12:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('identipy_app', '0024_searchgroup_params_obj'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searchgroup',
            name='parameters',
        ),
    ]
