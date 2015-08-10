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
import math


import sys
sys.path.append('../identipy/')
from identipy import main, utils
from multiprocessing import Process

def index(request, c=dict()):
    if request.user.is_authenticated():
        if(request.POST.get('runidentiprot')):
            request.POST = request.POST.copy()
            request.POST['runidentiprot'] = None
            c['runname'] = request.POST['runname']
            raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
            raw_config.read('latest_params_%d.cfg' % (c.get('paramtype', 3), ))
            c['SearchParametersForm'] = SearchParametersForm(request.POST, raw_config = raw_config)
            # c['SearchParametersForm'] =request.GET['SearchParametersForm']
            return identiprot_view(request, c = c)
        elif(request.POST.get('statusback')):
            request.POST = request.POST.copy()
            request.POST['statusback'] = None
            c['identiprotmessage'] = None
            return index(request, c=c)
        elif(request.POST.get('sbm')):
            request.POST = request.POST.copy()
            request.POST['sbm'] = None
            return files_view(request, c = c)
        elif(request.POST.get('cancel')):
            request.POST = request.POST.copy()
            request.POST['cancel'] = None
            return index(request, c=c)
        elif(request.POST.get('clear')):
            request.POST = request.POST.copy()
            request.POST['clear'] = None
            return index(request, c=dict())
        elif(request.POST.get('getstatus')):
            request.POST = request.POST.copy()
            request.POST['getstatus'] = None
            c['res_page'] = 1
            c['max_res_page'] = int(math.ceil(float(SearchGroup.objects.filter(userid=request.user.id).count()) / 10))
            return status(request, c = c)
        elif(request.POST.get('uploadform')):
            request.POST = request.POST.copy()
            request.POST['uploadform'] = None
            return upload(request, c = c)
        elif(request.POST.get('searchpage')):
            request.POST = request.POST.copy()
            request.POST['searchpage'] = None
            return searchpage(request, c = c)
        elif(request.POST.get('contacts')):
            request.POST = request.POST.copy()
            request.POST['contacts'] = None
            return contacts(request, c = c)
        elif(request.POST.get('uploadspectra')):
            request.POST = request.POST.copy()
            request.POST['uploadspectra'] = None
            return files_view_spectra(request, c = c)
        elif(request.POST.get('uploadfasta')):
            request.POST = request.POST.copy()
            request.POST['uploadfasta'] = None
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
            return getfiles(c=c)
        elif(request.GET.get('download_pepxml')):
            c['down_type'] = 'pepxml'
            return getfiles(c=c)
        elif(request.GET.get('download_mgf')):
            c['down_type'] = 'mgf'
            return getfiles(c=c)
        elif(request.GET.get('download_figs')):
            c['down_type'] = 'figs'
            return getfiles(c=c)
        elif(request.POST.get('prev_runs')):
            request.POST = request.POST.copy()
            request.POST['prev_runs'] = None
            c['res_page'] = c.get('res_page', 1) + 1
            return status(request, c=c)
        elif(request.POST.get('type1')):
            request.POST = request.POST.copy()
            request.POST['type1'] = None
            c['paramtype'] = 1
            return searchpage(request, c=c, upd=True)
        elif(request.POST.get('type2')):
            request.POST = request.POST.copy()
            request.POST['type2'] = None
            c['paramtype'] = 2
            return searchpage(request, c=c, upd=True)
        elif(request.POST.get('type3')):
            request.POST = request.POST.copy()
            request.POST['type3'] = None
            c['paramtype'] = 3
            return searchpage(request, c=c, upd=True)
        elif(request.POST.get('next_runs')):
            request.POST = request.POST.copy()
            request.POST['next_runs'] = None
            c['res_page'] = c.get('res_page', 1) - 1
            return status(request, c=c)
        c.update(csrf(request))
        # Handle file upload
        if request.method == 'POST' and request.POST.get('submit'):
            request.POST = request.POST.copy()
            request.POST['submit'] = None
            commonform = CommonForm(request.POST, request.FILES)
            if 'commonfiles' in request.FILES:#commonform.is_valid():
                for uploadedfile in request.FILES.getlist('commonfiles'):
                    fext = os.path.splitext(uploadedfile.name)[-1].lower()
                    if fext == '.mgf':
                        newdoc = SpectraFile(docfile = uploadedfile, userid = request.user)
                        newdoc.save()
                    if fext == '.fasta':
                        newdoc = FastaFile(docfile = uploadedfile, userid = request.user)
                        newdoc.save()
                    if fext == '.cfg':
                        os.remove('latest_params_%d.cfg' % (c.get('paramtype', 3), ))
                        fd = open('latest_params_%d.cfg' % (c.get('paramtype', 3), ), 'wb')
                        for chunk in uploadedfile.chunks():
                            fd.write(chunk)
                        fd.close()
                        newdoc = ParamsFile(docfile = uploadedfile, userid = request.user)
                        newdoc.save()
                    else:
                        pass
                return HttpResponseRedirect(reverse('datasets:index'))
            # return render(request, 'datasets/index.html', c)
        else:
            commonform = CommonForm()

        if 'chosenparams' in c:
            os.remove('latest_params_%d.cfg' % (c.get('paramtype', 3), ))
            shutil.copy(c['chosenparams'][0].docfile.name.encode('ASCII'), 'latest_params_%d.cfg' % (c.get('paramtype', 3), ))
            # for chunk in c['chosenparams'].chunks():
            #     fd.write(chunk)
            # fd.close()
        raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
        raw_config.read('latest_params_%d.cfg' % (c.get('paramtype', 3), ))

        if 'SearchParametersForm' not in c:
            sf = SearchParametersForm(raw_config=raw_config)
            # sf.add_params(raw_config=raw_config)
        else:
            sf = c['SearchParametersForm']
        c.update({'commonform': commonform, 'userid': request.user, 'SearchParametersForm': sf})
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
    if(request.POST.get('contacts')):
        request.POST = request.POST.copy()
        request.POST['contacts'] = None
        return contacts(request, c = {})
    if(request.POST.get('loginform')):
        request.POST = request.POST.copy()
        request.POST['loginform'] = None
        return loginview(request)
    if(request.POST.get('about')):
        request.POST = request.POST.copy()
        request.POST['about'] = None
        return about(request, c = {})
    return render_to_response('datasets/login.html', c)

def auth_and_login(request, onsuccess='/', onfail='/login/'):
    if(request.POST.get('contacts')):
        request.POST = request.POST.copy()
        request.POST['contacts'] = None
        return contacts(request, c = {})
    if(request.POST.get('loginform')):
        request.POST = request.POST.copy()
        request.POST['loginform'] = None
        return loginview(request)
    if(request.POST.get('about')):
        request.POST = request.POST.copy()
        request.POST['about'] = None
        return about(request, c = {})
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
    res_page = c.get('res_page', 1)
    # processes = SearchRun.objects.filter(userid=request.user.id).order_by('date_added')[::-1][:10]
    processes = SearchGroup.objects.filter(userid=request.user.id).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
    c.update({'processes': processes})
    return render(request, 'datasets/status.html', c)

def upload(request, c=dict()):
    c = c
    c.update(csrf(request))
    return render(request, 'datasets/upload.html', c)

def searchpage(request, c=dict(), upd=False):
    c = c
    c['paramtype'] = c.get('paramtype', 3)
    c.update(csrf(request))
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read('latest_params_%d.cfg' % (c.get('paramtype', 3), ))

    if upd or 'SearchParametersForm' not in c:
        sf = SearchParametersForm(raw_config=raw_config)
    else:
        sf = c['SearchParametersForm']
    c.update({'userid': request.user, 'SearchParametersForm': sf})
    return render(request, 'datasets/startsearch.html', c)

def contacts(request,c=dict()):
    c=c
    c.update(csrf(request))
    return render(request, 'datasets/contacts.html', c)

def about(request,c=dict()):
    c=c
    c.update(csrf(request))
    return render(request, 'datasets/index.html', c)
    
def files_view(request, usedclass=None, usedname=None, c=dict(), multiform=True):
    c = c
    c.update(csrf(request))
    if not usedclass or not usedname:
        usedclass=c['usedclass']
        usedname=c['usedname']
        del c['usedclass']
        del c['usedname']
    documents = usedclass.objects.filter(userid=request.user)
    cc = []
    for doc in documents:
        cc.append((doc.id, doc.name()))
    if request.POST.get('relates_to'):
        form = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
        if form.is_valid():
            chosenfilesids = [int(x) for x in form.cleaned_data.get('relates_to')]
            chosenfiles = usedclass.objects.filter(id__in=chosenfilesids)
            c.update({usedname: chosenfiles})
            return searchpage(request, c)
    else:
        form = MultFilesForm(custom_choices=cc, labelname=None, multiform=multiform)
    c.update({'form': form, 'usedclass': usedclass, 'usedname': usedname})
    return render_to_response('datasets/choose.html', c,
        context_instance=RequestContext(request))

def files_view_spectra(request, c):
    usedclass = SpectraFile
    return files_view(request, usedclass, 'chosenspectra', c = c)

def files_view_fasta(request, c):
    usedclass = FastaFile
    return files_view(request, usedclass, 'chosenfasta', c = c)

def files_view_params(request, c):
    usedclass = ParamsFile
    return files_view(request, usedclass, 'chosenparams', c = c)

def identiprot_view(request, c):
    c = runidentiprot(c)
    return index(request, c)

def runidentiprot(c):
    newgroup = SearchGroup(groupname=c['runname'], userid = c['userid'])
    newgroup.save()

    newgroup.add_files(c)

    def run_search(newrun, rn, c):
        paramfile = newrun.parameters.all()[0].path()
        fastafile = newrun.fasta.all()[0].path()
        settings = main.settings(paramfile)
        settings.set('input', 'database', fastafile.encode('ASCII'))
        settings.set('output', 'path', 'results/%s/%s' % (str(newrun.userid.id), rn.encode('ASCII')))
        totalrun(settings, newrun, c['userid'], paramfile)
        return 1

    def set_pepxml_path(settings, inputfile):
        if settings.has_option('output', 'path'):
            outpath = settings.get('output', 'path')
        else:
            outpath = path.dirname(inputfile)

        return path.join(outpath, path.splitext(path.basename(inputfile))[0] + path.extsep + 'pep' + path.extsep + 'xml')

    def totalrun(settings, newrun, usr, paramfile):
        procs = []
        spectralist = newrun.get_spectrafiles_paths()
        fastalist = newrun.get_fastafile_path()
        if not newrun.union:
            for obj in newrun.spectra.all():
                inputfile = obj.path()
                p = Process(target=runproc, args=(inputfile, settings, newrun, usr))
                p.start()
                procs.append(p)
            for p in procs:
                p.join()
            pepxmllist = newrun.get_pepxmlfiles_paths()
            paramlist = [paramfile]
            bname = pepxmllist[0].split('.pep.xml')[0]
        else:
            pepxmllist = newrun.get_pepxmlfiles_paths()
            paramlist = [paramfile]
            bname = os.path.dirname(pepxmllist[0]) + '/union'
        newrun.set_FDRs()
        from mpscore import MPscore
        MPscore.main(['_'] + pepxmllist + spectralist + fastalist + paramlist, union_custom=newrun.union)
        if not os.path.isfile(bname + '_PSMs.csv'):
            bname = os.path.dirname(bname) + '/union'

        dname = os.path.dirname(pepxmllist[0])
        for tmpfile in os.listdir(dname):
            if os.path.splitext(tmpfile)[-1] == '.png' and newrun.name() + '_' in os.path.basename(tmpfile):
                fl = open(os.path.join(dname, tmpfile))
                djangofl = File(fl)
                img = ResImageFile(docfile = djangofl, userid = usr)
                img.save()
                newrun.add_resimage(img)
                fl.close()
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
        filename = set_pepxml_path(settings, inputfile)
        utils.write_pepxml(inputfile, settings, main.process_file(inputfile, settings))
        fl = open(filename, 'r')
        djangofl = File(fl)
        pepxmlfile = PepXMLFile(docfile = djangofl, userid = usr)
        print filename
        pepxmlfile.docfile.name = filename
        pepxmlfile.save()
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
        c['identiprotmessage'] = 'Identiprot started'
    else:
        c['identiprotmessage'] = 'Results with name %s already exist, choose another name' % (rn.encode('ASCII'), )
    return c


def search_details(request, runname, c=dict()):
    c = c
    c.update(csrf(request))
    runobj = get_object_or_404(SearchGroup, groupname=runname)
    c.update({'searchgroup': runobj})
    return render(request, 'datasets/results.html', c)

def results_figure(request, runname, searchgroupid, c=dict()):
    c = c
    c.update(csrf(request))
    runobj = get_object_or_404(SearchRun, runname=runname, searchgroup_parent_id=searchgroupid)
    c.update({'searchrun': runobj})
    return render(request, 'datasets/results_figure.html', c)


def getfiles(c):
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
        elif c['down_type'] == 'figs':
            for down_fn in searchrun.get_resimage_paths():
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