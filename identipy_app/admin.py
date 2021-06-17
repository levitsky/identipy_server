from django.contrib import admin
from .models import SpectraFile, FastaFile


@admin.register(SpectraFile, FastaFile)
class FileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'date_added')
