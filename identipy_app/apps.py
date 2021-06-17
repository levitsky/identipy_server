from django.apps import AppConfig
from django.db.models.signals import post_save

class IdentipyAppConfig(AppConfig):
    name = 'identipy_app'

    def ready(self):
        from .signals import user_created
        from django.contrib.auth.models import User

        post_save.connect(user_created, sender=User, dispatch_uid='user_created')
