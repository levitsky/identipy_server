from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import SpectraFile, FastaFile, User


@admin.register(SpectraFile, FastaFile)
class FileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'date_added')

admin.site.register(User, UserAdmin)
