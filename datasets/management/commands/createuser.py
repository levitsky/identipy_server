from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from datasets.models import FastaFile

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

        user.save()