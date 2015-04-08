# -*- coding: utf-8 -*-
from django.core.context_processors import csrf
from django.shortcuts import render, get_object_or_404, render_to_response, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template import RequestContext

from .models import SpectraFile, RawFile, FastaFile#, Document
from .forms import DocumentForm, MultFilesForm
import os

def index(request):
    c = {}
    c.update(csrf(request))
    # Handle file upload
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            # newdoc = Document(docfile = request.FILES['docfile'], userid = request.user, fext = os.path.splitext(request.FILES['docfile'].name)[-1][1:])
            newdoc = SpectraFile(docfile = request.FILES['docfile'], userid = request.user)
            newdoc.save()

            # Redirect to the document list after POST
            return HttpResponseRedirect(reverse('datasets:index'))
    else:
        form = DocumentForm() # A empty, unbound form


    # Load documents for the list page
    # documents = Document.objects.filter(userid=request.user.id)
    documents = SpectraFile.objects.filter(userid=request.user.id)

    # Render list page with the documents and the form
    c.update({'documents': documents, 'form': form})
    return render(request, 'datasets/index.html', c)

def details(request, pK):
    doc = get_object_or_404(Document, id=pK)
    return render(request, 'datasets/details.html',
            {'document': doc})

def delete(request, pK):
    doc = get_object_or_404(Document, id=pK)
    doc.delete()
    return HttpResponseRedirect(reverse('datasets:index'))

def logout_view(request):
    logout(request)
    return loginview(request)

def loginview(request, message=None):
    c = {}
    c.update(csrf(request))
    c['message'] = message
    return render_to_response('datasets/login.html', c)

def auth_and_login(request, onsuccess='/', onfail='/login/'):
    user = authenticate(username=request.POST['email'], password=request.POST['password'])
    if user is not None:
        login(request, user)
        return redirect(onsuccess)
    else:
        return loginview(request, message='Wrong username or password')

def user_exists(username):
    user_count = User.objects.filter(username=username).count()
    if user_count == 0:
        return False
    return True

@login_required(login_url='datasets/login/')
def secured(request):
    c = {}
    c.update(csrf(request))
    c['username'] = request.user.username
    c['userid'] = request.user.id
    return render_to_response("index.html", c)


def files_view(request, usedclass):
    c = {}
    c.update(csrf(request))
    if request.method == 'POST':
        cc = [('A', 'AA'), ('B', 'BB'), ('C', 'CC')]
        # form = MultFilesForm(request.POST, custom_choices=cc, fextention=fextention)
        form = MultFilesForm(request.POST, custom_choices=cc)
        if form.is_valid():
            countries = form.cleaned_data.get('countries')
            # do something with your results
    else:
        # documents = Document.objects.filter(userid=request.user, fext=fextention)
        # documents = SpectraFile.objects.filter(userid=request.user)
        documents = usedclass.objects.filter(userid=request.user)
        cc = []
        for doc in documents:
            cc.append((doc.id, doc.name()))
        # documents = Document.objects.filter(format(fextention))
        # cc = [('d', 'dd'), ('g', 'gg'), ('h', 'hh')]
        # form = MultFilesForm(custom_choices=cc, fextention=fextention)
        form = MultFilesForm(custom_choices=cc)
    c.update({'form': form})
    return render_to_response('datasets/choose.html', c,
        context_instance=RequestContext(request))


def files_view_spectra(request):
    usedclass = SpectraFile
    return files_view(request, usedclass)