# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse

from .models import Document
from .forms import DocumentForm

def index(request):
    # Handle file upload
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            newdoc = Document(docfile = request.FILES['docfile'])
            newdoc.save()

            # Redirect to the document list after POST
            return HttpResponseRedirect(reverse('datasets:index'))
    else:
        form = DocumentForm() # A empty, unbound form

    # Load documents for the list page
    documents = Document.objects.all()

    # Render list page with the documents and the form
    return render(request, 'datasets/index.html',
        {'documents': documents, 'form': form})

def details(request, pK):
    doc = get_object_or_404(Document, id=pK)
    return HttpResponse(doc.docfile.name)

def delete(request, pK):
    doc = get_object_or_404(Document, id=pK)
    doc.delete()
    return HttpResponseRedirect(reverse('datasets:index'))
