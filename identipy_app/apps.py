from __future__ import unicode_literals

from django.apps import AppConfig
import logging
logger = logging.getLogger(__name__)

class IdentipyAppConfig(AppConfig):
    name = 'identipy_app'
    flag = False

    def ready(self):
        if self.flag:
            return
        self.flag = True
        # clean up lingrering runs
        SearchRun = self.get_model('SearchRun')
        try:
            runs = SearchRun.objects.exclude(status=SearchRun.FINISHED).exclude(status=SearchRun.DEAD)
            for r in runs:
                r.status = SearchRun.DEAD
                r.save()
                logger.info('Reaping run %s from %s by %s', r.id, r.searchgroup.groupname, r.searchgroup.user.username)
        except Exception as e:
            logger.error('Startup cleanup failed.\n%s', e)

