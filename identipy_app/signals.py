import os
from django.core.files import File

import logging
logger = logging.getLogger(__name__)

from .models import Protease, FastaFile, ParamsFile, Modification

def user_created(sender, **kwargs):
    user = kwargs['instance']
    if not kwargs['created']:
        logger.info('Detected a user edit, not creation. Signal handling skipped. User: %s (%s)',
            user.username, user.id)
        return
    logger.info('Handling new user %s.', user.username)

    df_dir = 'default_fasta'
    if os.path.isdir(df_dir):
        for flname in os.listdir(df_dir):
            fl = open(os.path.join(df_dir, flname))
            djangofl = File(fl)
            djangofl.name = os.path.basename(djangofl.name)
            fastaobj = FastaFile(docfile=djangofl, user=user)
            fastaobj.save()
            fl.close()
        logger.info('Added default FASTA for user %s.', user.username)

    for paramtype in [1, 2, 3]:
        fl = open('latest_params_%d.cfg' % paramtype)
        djangofl = File(fl)
        paramobj = ParamsFile(docfile=djangofl, user=user, type=paramtype)
        paramobj.save()
        fl.close()
    logger.info('Added default params for user %s.', user.username)

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
    logger.info('Added default proteases for user %s.', user.username)

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
    logger.info('Added default modifications for user %s.', user.username)

    for dirn in ['params', 'fasta', 'spectra']:
        d = os.path.join('uploads', dirn, str(user.id))
        if not os.path.isdir(d):
            os.makedirs(d)
            logger.info('Created %s.', d)
