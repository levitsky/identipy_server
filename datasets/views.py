# -*- coding: utf-8 -*-
from django.core.context_processors import csrf
from django.shortcuts import render, get_object_or_404, render_to_response, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core.files import File

from .models import SpectraFile, RawFile, FastaFile, SearchGroup, SearchRun, ParamsFile, PepXMLFile, ResImageFile, ResCSV#, Document
from .forms import SpectraForm, FastaForm, RawForm, MultFilesForm, ParamsForm
import os


def index(request, c=dict()):
    print request.method
    if(request.GET.get('runidentiprot')):
        request.GET = request.GET.copy()
        request.GET['runidentiprot'] = None
        c['runname'] = request.GET['runname']
        return identiprot_view(request, c = c)
    elif(request.GET.get('statusback')):
        request.GET = request.GET.copy()
        request.GET['statusback'] = None
        c['identiprotmessage'] = None
        return index(request, c=c)
    elif(request.GET.get('cancel')):
        request.GET = request.GET.copy()
        request.GET['cancel'] = None
        return index(request, c=c)
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
    elif(request.GET.get('search_details')):
        request.GET = request.GET.copy()
        return search_details(request, runname=request.GET['search_details'], c=c)
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
    # processes = SearchRun.objects.filter(userid=request.user.id).order_by('date_added')[::-1][:10]
    processes = SearchGroup.objects.filter(userid=request.user.id).order_by('date_added')[::-1][:10]
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

def identiprot_view(request, c):
    c = runidentiprot(c)
    return index(request, c)

def runidentiprot(c):
    import sys
    sys.path.append('../identipy/')
    from identipy import main, utils
    from multiprocessing import Process

    newgroup = SearchGroup(groupname=c['runname'], userid = c['userid'])
    newgroup.save()
    newgroup.add_files(c)
    # newrun = SearchRun(runname=c['runname'], userid = c['userid'])
    # newrun.save()
    # newrun.add_files(c)

    def totalrun(settings, newrun, usr):
        import subprocess
        procs = []
        for obj in newrun.spectra.all():
            inputfile = obj.path()
            # newrun.calc_msms(inputfile)
            p = Process(target=runproc, args=(inputfile, settings, newrun, usr))
            p.start()
            procs.append(p)
        for p in procs:
            p.join()
        # newrun = get_object_or_404(SearchRun, id=pK)#SearchRun(runname=c['runname'], userid = c['userid'])
        pepxmllist = newrun.get_pepxmlfiles_paths()
        spectralist = newrun.get_spectrafiles_paths()
        fastalist = newrun.get_fastafile_path()
        paramlist = ['defaultMP.cfg']#newrun.get_paramfile_path()
        # print ['python2', '../mp-score/MPscore.py'] + pepxmllist + spectralist + fastalist + paramlist
        subprocess.call(['python2', '../mp-score/MPscore.py'] + pepxmllist + spectralist + fastalist + paramlist)
        bname = pepxmllist[0].split('.pep.xml')[0]
        if os.path.exists(bname + '.png'):
            fl = open(bname + '.png')
            djangofl = File(fl)
            img = ResImageFile(docfile = djangofl, userid = usr)
            img.save()
            newrun.add_resimage(img)
        if os.path.exists(bname + '_PSMs.csv'):
            fl = open(bname + '_PSMs.csv')
            djangofl = File(fl)
            csvf = ResCSV(docfile = djangofl, userid = usr, ftype='psm')
            csvf.save()
            newrun.add_rescsv(csvf)
        if os.path.exists(bname + '_peptides.csv'):
            fl = open(bname + '_peptides.csv')
            djangofl = File(fl)
            csvf = ResCSV(docfile = djangofl, userid = usr, ftype='peptide')
            csvf.save()
            newrun.add_rescsv(csvf)
        if os.path.exists(bname + '_proteins.csv'):
            fl = open(bname + '_proteins.csv')
            djangofl = File(fl)
            csvf = ResCSV(docfile = djangofl, userid = usr, ftype='protein')
            csvf.save()
            newrun.add_rescsv(csvf)
        newrun.calc_results()
        newrun.change_status('Task is finished')
        newrun.save()

    def runproc(inputfile, settings, newrun, usr):
        from os import path
        newrun.change_status('Search is running')
        if settings.has_option('output', 'path'):
            outpath = settings.get('output', 'path')
        else:
            outpath = path.dirname(inputfile)

        filename = path.join(outpath, path.splitext(path.basename(inputfile))[0] + path.extsep + 'pep' + path.extsep + 'xml')
        utils.write_pepxml(inputfile, settings, main.process_file(inputfile, settings))
        fl = open(filename, 'r')
        djangofl = File(fl)
        pepxmlfile = PepXMLFile(docfile = djangofl, userid = usr)
        print filename
        pepxmlfile.docfile.name = filename
        pepxmlfile.save()
        print pepxmlfile.docfile.name
        newrun.add_pepxml(pepxmlfile)
        newrun.change_status('Post-search validation is running')
        # newrun.save()
        return 1

    rn = newgroup.name()
    if not os.path.exists('results'):
        os.mkdir('results')
    if not os.path.exists(os.path.join('results', str(newgroup.userid.id))):
        os.mkdir(os.path.join('results', str(newgroup.userid.id)))
    if not os.path.exists('results/%s/%s' % (str(newgroup.userid.id), rn.encode('ASCII'))):
        os.mkdir('results/%s/%s' % (str(newgroup.userid.id), rn.encode('ASCII')))
        for newrun in newgroup.get_searchruns():
            paramfile = newrun.parameters.all()[0].path()
            fastafile = newrun.fasta.all()[0].path()
            settings = main.settings(paramfile)
            settings.set('input', 'database', fastafile.encode('ASCII'))
            settings.set('output', 'path', 'results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII')))
            p = Process(target=totalrun, args=(settings, newrun, c['userid']))
            p.start()
        c['identiprotmessage'] = 'Identiprot was started'
    else:
        c['identiprotmessage'] = 'Results with name %s already exists, choose another name' % (rn.encode('ASCII'), )
    return c


def search_details(request, runname, c=dict()):
    # doc = get_object_or_404(Document, id=pK)
    c = c
    c.update(csrf(request))
    runobj = get_object_or_404(SearchRun, runname=runname)
    c.update({'searchrun': runobj})
    return render(request, 'datasets/results.html', c)