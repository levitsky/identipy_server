from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from datasets.models import FastaFile, ParamsFile, Protease

from pyteomics import parser
from os import path, listdir

class Command(BaseCommand):
    help = 'Creates new user'

    def add_arguments(self, parser):
        parser.add_argument('user_name', type=str)
        parser.add_argument('passwd', type=str)

    def handle(self, *args, **options):
        user_name = options['user_name']
        user_passwd = options['passwd']
        user = User.objects.create_user(user_name, user_name, user_passwd)

        df_dir = 'default_fasta'
        for flname in listdir(df_dir):
            fl = open(path.join(df_dir, flname))
            djangofl = File(fl)
            fastaobj = FastaFile(docfile = djangofl, userid = user)
            fastaobj.save()
            fl.close()

        for paramtype in [1, 2, 3]:
            fl = open('latest_params_%d.cfg' % (paramtype, ))
            djangofl = File(fl)
            paramobj = ParamsFile(docfile = djangofl, userid = user, type=paramtype)
            paramobj.save()
            fl.close()

        priority_list = ['pepsin ph2.0', 'glutamyl endopeptidase', 'ntcb', 'cnbr', 'lysc', 'trypsin']
        for protease in parser.expasy_rules:
            bonus = priority_list.index(protease) + 1 if protease in priority_list else 0
            protease_object = Protease(name=protease, rule=parser.expasy_rules[protease], order_val=1+bonus, user=user)
            protease_object.save()

        user.save()