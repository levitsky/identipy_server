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

from .models import SpectraFile, RawFile, FastaFile, SearchGroup, SearchRun, ParamsFile, PepXMLFile, ResImageFile, ResCSV
from .forms import MultFilesForm, CommonForm, SearchParametersForm
import os
from os import path
import subprocess
import zipfile
import StringIO
import shutil


import sys
sys.path.append('../identipy/')
from identipy import main, utils
from multiprocessing import Process

def index(request, c=dict()):
    if request.user.is_authenticated():
        print request.method
        if(request.POST.get('runidentiprot')):
            request.POST = request.POST.copy()
            request.POST['runidentiprot'] = None
            c['runname'] = request.POST['runname']
            print request.POST.keys(), 'Req, POST, keys'
            raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
            raw_config.read('latest_params.cfg')
            c['SearchParametersForm'] = SearchParametersForm(request.POST, raw_config = raw_config)
            # c['SearchParametersForm'] =request.GET['SearchParametersForm']
            return identiprot_view(request, c = c)
        elif(request.POST.get('testform')):
            request.POST = request.POST.copy()
            request.POST['testform'] = None
            print request.POST.keys(), 'Req, POST, keys'
            raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
            raw_config.read('latest_params.cfg')
            c['SearchParametersForm'] = SearchParametersForm(request.POST, raw_config = raw_config)
            return render(request, 'datasets/index.html', c)
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
        elif(request.GET.get('results_figure')):
            request.GET = request.GET.copy()
            return results_figure(request, runname=request.GET['results_figure_actualname'], searchgroupid=request.GET['results_figure_searchgroupid'], c=c)
        elif(request.GET.get('download_csv')):
            c['down_type'] = 'csv'
            return getfiles(request, c=c)
        elif(request.GET.get('download_pepxml')):
            c['down_type'] = 'pepxml'
            return getfiles(request, c=c)
        elif(request.GET.get('download_mgf')):
            c['down_type'] = 'mgf'
            return getfiles(request, c=c)
        c.update(csrf(request))
        # Handle file upload
        if request.method == 'POST':
            commonform = CommonForm(request.POST, request.FILES)
            if 'commonfiles' in request.FILES:#commonform.is_valid():
                print 'HERE !@$!@!$!$@!$'
                for uploadedfile in request.FILES.getlist('commonfiles'):
                    fext = os.path.splitext(uploadedfile.name)[-1].lower()
                    if fext == '.mgf':
                        newdoc = SpectraFile(docfile = uploadedfile, userid = request.user)
                        newdoc.save()
                    if fext == '.fasta':
                        newdoc = FastaFile(docfile = uploadedfile, userid = request.user)
                        newdoc.save()
                    if fext == '.cfg':
                        os.remove('latest_params.cfg')
                        fd = open('latest_params.cfg', 'wb')
                        for chunk in uploadedfile.chunks():
                            fd.write(chunk)
                        fd.close()
                        # uploadedfile.write('latest_params.cfg')
                        newdoc = ParamsFile(docfile = uploadedfile, userid = request.user)
                        newdoc.save()
                    else:
                        pass
                return HttpResponseRedirect(reverse('datasets:index'))
        else:
            commonform = CommonForm()

        if 'chosenparams' in c:
            os.remove('latest_params.cfg')
            shutil.copy(c['chosenparams'][0].docfile.name.encode('ASCII'), 'latest_params.cfg')
            # fd = open('latest_params.cfg', 'wb')
            # for chunk in c['chosenparams'].chunks():
            #     fd.write(chunk)
            # fd.close()
        raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
        raw_config.read('latest_params.cfg')

        if 'SearchParametersForm' not in c:
            print 'HERE!Q'
            sf = SearchParametersForm(raw_config=raw_config)
            # sf.add_params(raw_config=raw_config)
        else:
            sf = c['SearchParametersForm']
        print sf.fields
        c.update({'commonform': commonform, 'userid': request.user, 'SearchParametersForm': sf})
        print 'Here!'
        return render(request, 'datasets/index.html', c)
    else:
        return redirect('/login/')

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
    newgroup = SearchGroup(groupname=c['runname'], userid = c['userid'])
    newgroup.save()

    # print ParamsFile.objects.filter(userid=newgroup.userid).count(), 'Number of params objects'
    # print ParamsFile.objects.filter(docfile__endswith='latest_params.cfg', userid=newgroup.userid).count()
    # fl = open('latest_params.cfg')
    # djangofl = File(fl)

    # for v in c['SearchParametersForm']:
    #     print v.name, v.value()

    # newdoc = ParamsFile(docfile = djangofl, userid = c['userid'])
    # newdoc.save()
    # fl.close()
    # c['chosenparams'] = [newdoc, ] # TODO
    newgroup.add_files(c)
    # newrun = SearchRun(runname=c['runname'], userid = c['userid'])
    # newrun.save()
    # newrun.add_files(c)

    def run_search(newrun, rn, c):
        paramfile = newrun.parameters.all()[0].path()
        fastafile = newrun.fasta.all()[0].path()
        settings = main.settings(paramfile)
        settings.set('input', 'database', fastafile.encode('ASCII'))
        settings.set('output', 'path', 'results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII')))
        totalrun(settings, newrun, c['userid'])
        # p = Process(target=totalrun, args=(settings, newrun, c['userid']))
        # p.start()
        # p.join()
        return 1

    def set_pepxml_path(settings, inputfile):
        if settings.has_option('output', 'path'):
            outpath = settings.get('output', 'path')
        else:
            outpath = path.dirname(inputfile)

        return path.join(outpath, path.splitext(path.basename(inputfile))[0] + path.extsep + 'pep' + path.extsep + 'xml')

    def totalrun(settings, newrun, usr):
        procs = []
        spectralist = newrun.get_spectrafiles_paths()
        fastalist = newrun.get_fastafile_path()
        if not newrun.union:
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
            paramlist = ['defaultMP.cfg']#newrun.get_paramfile_path()
            bname = pepxmllist[0].split('.pep.xml')[0]
        else:
            # pepxmllist = [set_pepxml_path(settings, s) for s in spectralist]
            pepxmllist = newrun.get_pepxmlfiles_paths()
            paramlist = ['defaultMP2.cfg']
            bname = os.path.dirname(pepxmllist[0]) + '/union'
        # print ['python2', '../mp-score/MPscore.py'] + pepxmllist + spectralist + fastalist + paramlist
        subprocess.call(['python2', '../mp-score/MPscore.py'] + pepxmllist + spectralist + fastalist + paramlist)
        # bname = pepxmllist[0].split('.pep.xml')[0]
        if not os.path.isfile(bname + '_PSMs.csv'):
            bname = os.path.dirname(bname) + '/union'

        dname = os.path.dirname(pepxmllist[0])
        for tmpfile in os.listdir(dname):
            if os.path.splitext(tmpfile)[-1] == '.png':
                fl = open(os.path.join(dname, tmpfile))
                djangofl = File(fl)
                img = ResImageFile(docfile = djangofl, userid = usr)
                img.save()
                newrun.add_resimage(img)
                fl.close()
        # if os.path.exists(bname + '.png'):
        #     fl = open(bname + '.png')
        #     djangofl = File(fl)
        #     img = ResImageFile(docfile = djangofl, userid = usr)
        #     img.save()
        #     newrun.add_resimage(img)
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
        return 1

    def runproc(inputfile, settings, newrun, usr):
        # if settings.has_option('output', 'path'):
        #     outpath = settings.get('output', 'path')
        # else:
        #     outpath = path.dirname(inputfile)
        #
        # filename = path.join(outpath, path.splitext(path.basename(inputfile))[0] + path.extsep + 'pep' + path.extsep + 'xml')
        filename = set_pepxml_path(settings, inputfile)
        utils.write_pepxml(inputfile, settings, main.process_file(inputfile, settings))
        fl = open(filename, 'r')
        djangofl = File(fl)
        pepxmlfile = PepXMLFile(docfile = djangofl, userid = usr)
        print filename
        pepxmlfile.docfile.name = filename
        pepxmlfile.save()
        print pepxmlfile.docfile.name
        newrun.add_pepxml(pepxmlfile)
        return 1

    def start_union(newgroup, rn, c):
        try:
            un_run = newgroup.get_union()[0]
        except:
            un_run = False
        if un_run:
            for newrun in newgroup.get_searchruns():
                for pepf in newrun.get_pepxmlfiles():
                    un_run.add_pepxml(pepf)
                    un_run.save()
            run_search(un_run, rn, c)
        newgroup.change_status('Task is finished')

    def start_all(newgroup, rn, c):
        tmp_procs = []
        for newrun in newgroup.get_searchruns():
            p = Process(target=run_search, args=(newrun, rn, c))
            p.start()
            tmp_procs.append(p)
            # paramfile = newrun.parameters.all()[0].path()
            # fastafile = newrun.fasta.all()[0].path()
            # settings = main.settings(paramfile)
            # settings.set('input', 'database', fastafile.encode('ASCII'))
            # settings.set('output', 'path', 'results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII')))
            # p = Process(target=totalrun, args=(settings, newrun, c['userid']))
            # p.start()
        for p in tmp_procs:
            p.join()
        p = Process(target=start_union, args=(newgroup, rn, c))
        p.start()

    rn = newgroup.name()
    if not os.path.exists('results'):
        os.mkdir('results')
    if not os.path.exists(os.path.join('results', str(newgroup.userid.id))):
        os.mkdir(os.path.join('results', str(newgroup.userid.id)))
    if not os.path.exists('results/%s/%s' % (str(newgroup.userid.id), rn.encode('ASCII'))):
        os.mkdir('results/%s/%s' % (str(newgroup.userid.id), rn.encode('ASCII')))
        newgroup.change_status('Search is running')
        p = Process(target=start_all, args=(newgroup, rn, c))
        p.start()
        c['identiprotmessage'] = 'Identiprot was started'
    else:
        c['identiprotmessage'] = 'Results with name %s already exists, choose another name' % (rn.encode('ASCII'), )
    return c


def search_details(request, runname, c=dict()):
    # doc = get_object_or_404(Document, id=pK)
    c = c
    c.update(csrf(request))
    # runobj = get_object_or_404(SearchRun, runname=runname)
    # c.update({'searchrun': runobj})
    runobj = get_object_or_404(SearchGroup, groupname=runname)
    c.update({'searchgroup': runobj})
    return render(request, 'datasets/results.html', c)

def results_figure(request, runname, searchgroupid, c=dict()):
    # doc = get_object_or_404(Document, id=pK)
    c = c
    c.update(csrf(request))
    # runobj = get_object_or_404(SearchRun, runname=runname)
    # c.update({'searchrun': runobj})
    runobj = get_object_or_404(SearchRun, runname=runname, searchgroup_parent_id=searchgroupid)
    c.update({'searchrun': runobj})
    return render(request, 'datasets/results_figure.html', c)


def getfiles(request, c):
    searchgroup = c['searchgroup']
    filenames = []
    for searchrun in searchgroup.get_searchruns_all():
        if c['down_type'] == 'csv':
            for down_fn in searchrun.get_csvfiles_paths():
                filenames.append(down_fn)
        elif c['down_type'] == 'pepxml':
            for down_fn in searchrun.get_pepxmlfiles_paths():
                filenames.append(down_fn)
        elif c['down_type'] == 'mgf':
            for down_fn in searchrun.get_spectrafiles_paths():
                filenames.append(down_fn)

    zip_subdir = searchgroup.name() + '_' + c['down_type'] + '_files'
    zip_filename = "%s.zip" % zip_subdir

    s = StringIO.StringIO()
    zf = zipfile.ZipFile(s, "w")

    for fpath in filenames:
        fdir, fname = os.path.split(fpath)
        zip_path = os.path.join(zip_subdir, fname)
        zf.write(fpath, zip_path)
    zf.close()

    resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
    resp['Content-Disposition'] = 'attachment; filename=%s' % zip_filename

    return resp