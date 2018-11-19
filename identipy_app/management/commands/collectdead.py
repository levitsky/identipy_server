from django.core.management.base import BaseCommand
import logging
from identipy_app.models import SearchRun

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sets status of lingering runs to DEAD'

    def handle(self, *args, **options):
        try:
            runs = SearchRun.objects.exclude(status=SearchRun.FINISHED).exclude(status=SearchRun.DEAD)
            for r in runs:
                r.status = SearchRun.DEAD
                r.save()
                logger.info('Reaping run %s from %s by %s', r.id, r.searchgroup.groupname, r.searchgroup.user.username)
        except Exception as e:
            logger.error('Startup cleanup failed.\n%s', e)
     
