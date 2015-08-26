from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from datasets.models import FastaFile, ParamsFile, Protease, Modification

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
            djangofl.name = path.basename(djangofl.name)
            fastaobj = FastaFile(docfile = djangofl, user = user)
            fastaobj.save()
            fl.close()

        for paramtype in [1, 2, 3]:
            fl = open('latest_params_%d.cfg' % (paramtype, ))
            djangofl = File(fl)
            paramobj = ParamsFile(docfile = djangofl, user = user, type=paramtype)
            paramobj.save()
            fl.close()

        priority_list = ['pepsin ph2.0', 'glutamyl endopeptidase', 'ntcb', 'cnbr', 'lysc', 'trypsin']
        for protease in parser.expasy_rules:
            bonus = priority_list.index(protease) + 1 if protease in priority_list else 0
            protease_object = Protease(name=protease, rule=parser.expasy_rules[protease], order_val=1+bonus, user=user)
            protease_object.save()

        default_mods = [
            ['camC', 'cam', 57.022, 'C'],
            ['oxM', 'ox', 15.994915, 'M'],
            ['oxW', 'ox', 15.994915, 'W'],
            ['ac[', 'ac', 42.010565, '['],
            ['acK', 'ac', 42.010565, 'K'],
            ['pS', 'p', 79.966331, 'S'],
            ['pT', 'p', 79.966331, 'T'],
            ['pY', 'p', 79.966331, 'Y'],
        ]
        for mod in default_mods:
            mod_object = Modification(name=mod[0], label=mod[1], mass=mod[2], aminoacid=mod[3], user=user)
            mod_object.save()
        user.save()