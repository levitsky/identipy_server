from django.contrib import admin
from .models import SpectraFile, RawFile, FastaFile#,Document
from django.conf import settings
import os
os.chdir(settings.BASE_DIR)

# admin.site.register(Document)
admin.site.register(SpectraFile)
admin.site.register(RawFile)
admin.site.register(FastaFile)
