from django.core.management.base import BaseCommand
from ...models import User

from getpass import getpass
from django.conf import settings
import os
os.chdir(settings.BASE_DIR)

class Command(BaseCommand):
    help = 'Creates new user'

    def add_arguments(self, parser):
        parser.add_argument('user_name', type=str)
        parser.add_argument('email', nargs='?', type=str)
        parser.add_argument('passwd', nargs='?', type=str)

    def handle(self, *args, **options):
        user_name = options['user_name']
        email = options['email']
        user_passwd = options['passwd']
        if not user_passwd:
            user_passwd = getpass('Enter the user password: ')

        User.objects.create_user(user_name, email, user_passwd)
