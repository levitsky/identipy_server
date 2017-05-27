from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from identipy_app.models import FastaFile, ParamsFile, Protease, Modification

from pyteomics import parser
from os import path, listdir
from django.conf import settings
import os
os.chdir(settings.BASE_DIR)

class Command(BaseCommand):
    help = 'Creates new user'

    def add_arguments(self, parser):
        parser.add_argument('user_name', type=str)
        parser.add_argument('email', type=str)
        parser.add_argument('passwd', type=str)

    def handle(self, *args, **options):
        user_name = options['user_name']
        email = options['email']
        user_passwd = options['passwd']

        user = User.objects.create_user(user_name, email, user_passwd)

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

        default_proteases = [
            ['trypsin', '[KR]|{P}'],
            ['lysc', '[K]|[X]'],
            ['cnbr', '[M]|[X]'],
            ['ntcb', '[X]|[C]'],
            ['gluc', '[E]|[X]'],
            ['pepsin ph2', '[FL]|{P}'],
            ['pepsin ph1.3', '[FLWY]|{P}'],
            ['iodosobenzoic acid', '[W]|[X]'],
            ['bnps-skatole', '[W]|[X]'],
            ['arg-c', '[R]|[X]'],
            ['arg-n', '[X]|[D]']
        ]

        for idx, protease in enumerate(default_proteases[::-1]):
            protease_object = Protease(name=protease[0], rule=protease[1], order_val=1+idx, user=user)
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
            ['waterlossE', 'wl', -18.0106, '[E'],
            ['ammoniumlossQ', 'al', -17.0265, '[Q'],
            ['ammoniumlossC', 'al', -17.0265, '[C'],
        ]
        for mod in default_mods:
            mod_object = Modification(name=mod[0], label=mod[1], mass=mod[2], aminoacid=mod[3], user=user)
            mod_object.save()
        user.save()

        for dirn in ['params', 'fasta', 'spectra']:
            d = os.path.join('uploads', dirn, str(user.id))
            if not os.path.isdir(d):
                os.makedirs(d)
