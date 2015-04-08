from django.contrib import admin
from .models import SpectraFile, RawFile, FastaFile#,Document

# admin.site.register(Document)
admin.site.register(SpectraFile)
admin.site.register(RawFile)
admin.site.register(FastaFile)
