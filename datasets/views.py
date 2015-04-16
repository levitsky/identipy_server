# -*- coding: utf-8 -*-
from django.core.context_processors import csrf
from django.shortcuts import render, get_object_or_404, render_to_response, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template import RequestContext

from .models import SpectraFile, RawFile, FastaFile, SearchRun, ParamsFile#, Document
from .forms import SpectraForm, FastaForm, RawForm, MultFilesForm, ParamsForm
import os


def index(request, c=dict()):
    print request.method
    if(request.GET.get('runidentipy')):
        request.GET = request.GET.copy()
        request.GET['runidentipy'] = None
        c['runname'] = request.GET['runname']
        return identipy_view(request, c = c)
    elif(request.GET.get('statusback')):
        request.GET = request.GET.copy()
        request.GET['statusback'] = None
        c['identipymessage'] = None
        return index(request, c=dict())
    elif(request.GET.get('clear')):
        request.GET = request.GET.copy()
        request.GET['clear'] = None
        return index(request, c=dict())
    elif(request.GET.get('getstatus')):
        request.GET = request.GET.copy()
        request.GET['getstatus'] = None
        return status(request, c = c)
    elif(request.GET.get('uploadspectra')):
        request.GET = request.GET.copy()
        request.GET['uploadspectra'] = None
        return files_view_spectra(request, c = c)
    elif(request.GET.get('uploadfasta')):
        request.GET = request.GET.copy()
        request.GET['uploadfasta'] = None
        return files_view_fasta(request, c = c)
    elif(request.GET.get('uploadparams')):
        request.GET = request.GET.copy()
        request.GET['uploadparams'] = None
        return files_view_params(request, c = c)
    c.update(csrf(request))
    # Handle file upload
    if request.method == 'POST':
        # form = DocumentForm(request.POST, request.FILES)
        spectraform = SpectraForm(request.POST, request.FILES)
        fastaform = FastaForm(request.POST, request.FILES)
        rawform = RawForm(request.POST, request.FILES)
        paramsform = ParamsForm(request.POST, request.FILES)
        if fastaform.is_valid():
            # newdoc = Document(docfile = request.FILES['docfile'], userid = request.user, fext = os.path.splitext(request.FILES['docfile'].name)[-1][1:])
            newdoc = FastaFile(docfile = request.FILES['fastafile'], userid = request.user)
            newdoc.save()
            # Redirect to the document list after POST
            return HttpResponseRedirect(reverse('datasets:index'))
        if spectraform.is_valid():
            # newdoc = Document(docfile = request.FILES['docfile'], userid = request.user, fext = os.path.splitext(request.FILES['docfile'].name)[-1][1:])
            newdoc = SpectraFile(docfile = request.FILES['spectrafile'], userid = request.user)
            newdoc.save()
            # Redirect to the document list after POST
            return HttpResponseRedirect(reverse('datasets:index'))
        if paramsform.is_valid():
            # newdoc = Document(docfile = request.FILES['docfile'], userid = request.user, fext = os.path.splitext(request.FILES['docfile'].name)[-1][1:])
            newdoc = ParamsFile(docfile = request.FILES['paramsfile'], userid = request.user)
            newdoc.save()
            # Redirect to the document list after POST
            return HttpResponseRedirect(reverse('datasets:index'))
    else:
        spectraform = SpectraForm() # A empty, unbound form
        fastaform = FastaForm()
        rawform = RawForm()
        paramsform = ParamsForm()


    # Load documents for the list page
    # documents = Document.objects.filter(userid=request.user.id)
    documents = SpectraFile.objects.filter(userid=request.user.id)

    # Render list page with the documents and the form
    c.update({'documents': documents, 'spectraform': spectraform, 'fastaform': fastaform, 'rawform': rawform, 'paramsform': paramsform, 'userid': request.user})
    return render(request, 'datasets/index.html', c)

def details(request, pK):
    # doc = get_object_or_404(Document, id=pK)
    doc = get_object_or_404(SpectraFile, id=pK)
    return render(request, 'datasets/details.html',
            {'document': doc})

def delete(request, pK):
    # doc = get_object_or_404(Document, id=pK)
    doc = get_object_or_404(SpectraFile, id=pK)
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


def status(request, c=dict()):
    c = c
    c.update(csrf(request))
    processes = SearchRun.objects.filter(userid=request.user.id).order_by('date_added')[::-1][:10]
    c.update({'processes': processes})
    return render(request, 'datasets/status.html', c)

def files_view(request, usedclass, usedname, labelname=None, c=dict(), multiform=True):
    c = c
    c.update(csrf(request))
    documents = usedclass.objects.filter(userid=request.user)
    cc = []
    for doc in documents:
        cc.append((doc.id, doc.name()))
    if request.method == 'POST':
        # cc = [('A', 'AA'), ('B', 'BB'), ('C', 'CC')]
        # form = MultFilesForm(request.POST, custom_choices=cc, fextention=fextention)
        # form = MultFilesForm(request.POST, custom_choices=cc)
        form = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
        if form.is_valid():
            chosenfilesids = [int(x) for x in form.cleaned_data.get('relates_to')]
            chosenfiles = usedclass.objects.filter(id__in=chosenfilesids)
            c.update({usedname: chosenfiles})
            return index(request, c)
            # return render(request, 'datasets/index.html', c)
            # print chosenfiles
            # do something with your results
    else:
        # documents = Document.objects.filter(userid=request.user, fext=fextention)
        # documents = SpectraFile.objects.filter(userid=request.user)
        # documents = Document.objects.filter(format(fextention))
        # cc = [('d', 'dd'), ('g', 'gg'), ('h', 'hh')]
        # form = MultFilesForm(custom_choices=cc, fextention=fextention)
        form = MultFilesForm(custom_choices=cc, labelname=None, multiform=multiform)
    c.update({'form': form})
    return render_to_response('datasets/choose.html', c,
        context_instance=RequestContext(request))

def files_view_spectra(request, c):
    usedclass = SpectraFile
    return files_view(request, usedclass, 'chosenspectra', labelname='Choose spectra files', c = c)

def files_view_fasta(request, c):
    usedclass = FastaFile
    return files_view(request, usedclass, 'chosenfasta', labelname='Choose fasta file', c = c)

def files_view_params(request, c):
    usedclass = ParamsFile
    return files_view(request, usedclass, 'chosenparams', labelname='Choose parameters file', c = c)

def identipy_view(request, c):
    c = runidentipy(c)
    return index(request, c)

def runidentipy(c):
    import sys
    sys.path.append('../identipy/')
    from identipy import main, utils
    from multiprocessing import Process

    newrun = SearchRun(runname=c['runname'], userid = c['userid'])
    newrun.save()
    newrun.add_files(c)

    def runproc(inputfile, settings, newrun):
        newrun.change_status('Task is running')
        utils.write_pepxml(inputfile, settings, main.process_file(inputfile, settings))
        newrun.change_status('Task finished')

    paramfile = newrun.parameters.all()[0].path()
    fastafile = newrun.fasta.all()[0].path()
    rn = newrun.runname
    settings = main.settings(paramfile)
    settings.set('input', 'database', fastafile.encode('ASCII'))
    if not os.path.exists('results'):
        os.mkdir('results')
    if not os.path.exists(os.path.join('results', str(newrun.userid.id))):
        os.mkdir(os.path.join('results', str(newrun.userid.id)))
    if not os.path.exists('results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII'))):
        os.mkdir('results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII')))
        settings.set('output', 'path', 'results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII')))
        for obj in newrun.spectra.all():
            inputfile = obj.path()
            p = Process(target=runproc, args=(inputfile, settings, newrun))
            p.start()
        c['identipymessage'] = 'Identipy was started'
    else:
        c['identipymessage'] = 'Results with name %s already exists, choose another name' % (rn.encode('ASCII'), )
    return c


def search_details(request, pK, c=dict()):
    # doc = get_object_or_404(Document, id=pK)
    c = c
    c.update(csrf(request))
    runobj = get_object_or_404(SearchRun, id=pK)
    c.update({'searchrun': runobj})
    return render(request, 'datasets/results.html', c)