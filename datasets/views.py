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
from django.core.mail import send_mail, BadHeaderError
from django.contrib import messages
from django.db.models import Max

from .models import SpectraFile, RawFile, FastaFile, SearchGroup, SearchRun, ParamsFile, PepXMLFile, ResImageFile, ResCSV, Protease, Modification
from .forms import MultFilesForm, CommonForm, SearchParametersForm, ContactForm, AddProteaseForm, AddModificationForm
import os
from os import path
import subprocess
import zipfile
import StringIO
import shutil
import math
from copy import copy

from pyteomics import parser
import sys
sys.path.append('../identipy/')
from identipy import main, utils
from multiprocessing import Process
from aux import save_mods, save_params_new, Menubar, ResultsDetailed

def update_searchparams_form_new(request, paramtype, sftype):
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(get_user_latest_params_path(paramtype, request.user))
    return SearchParametersForm(raw_config=raw_config, user=request.user, label_suffix='', sftype=sftype, prefix=sftype)

def update_searchparams_form(request, c):
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(get_user_latest_params_path(c.get('paramtype', 3), c.get('userid', None)) )
    c['SearchParametersForm'] = SearchParametersForm(raw_config=raw_config, user=request.user, label_suffix='')
    return c

def get_forms(request, c):
    c['userid'] = request.user
    c['paramtype'] = c.get('paramtype', 3)
    if c.get('SearchForms', None):
        for sf in c['SearchForms'].values():
            if any(sf.sftype + '-' + v.name in request.POST for v in sf):
                save_params_new(c['SearchForms'], c['userid'], paramsname=False, paramtype=c.get('paramtype', 3), request=request)
                c['SearchForms'][sf.sftype] = update_searchparams_form_new(request=request, paramtype=c['paramtype'], sftype=sf.sftype)
    else:
        c['SearchForms'] = {}
        for sftype in ['main'] + (['postsearch'] if c.get('paramtype', 3) == 3 else []):
            c['SearchForms'][sftype] = update_searchparams_form_new(request=request, paramtype=c['paramtype'], sftype=sftype)
    return c

def index(request, c=dict()):
    if request.user.is_authenticated():
        print request.POST.items()
        c = get_forms(request, c)
        # if 'SearchParametersForm' in c:
        #     if any(v.name in request.POST for v in c['SearchParametersForm']):
        #         save_params(c['SearchParametersForm'], c['userid'], paramsname=False, paramtype=c.get('paramtype', 3), request=request)
        #         c = update_searchparams_form(request=request, c=c)
        # else:
        #     c = update_searchparams_form(request=request, c=c)
        if(request.POST.get('runidentiprot')):
            request.POST = request.POST.copy()
            request.POST['runidentiprot'] = None
            c['runname'] = request.POST['runname']
            return identiprot_view(request, c = c)
        elif(request.POST.get('statusback')):
            request.POST = request.POST.copy()
            request.POST['statusback'] = None
            return index(request, c=c)
        elif(request.POST.get('sbm')):
            request.POST = request.POST.copy()
            request.POST['sbm'] = None
            if c.get('sbm_modform', False):
                c['sbm_modform'] = False
                return select_modifications(request, c, fixed=c['fixed'], upd=True)
            else:
                return files_view(request, c = c)
        elif(request.POST.get('del')):
            request.POST = request.POST.copy()
            request.POST['del'] = None
            return delete(request, c = c)
        elif(request.POST.get('cancel')):
            request.POST = request.POST.copy()
            request.POST['cancel'] = None
            return index(request, c=c)
        elif(request.POST.get('clear')):
            request.POST = request.POST.copy()
            request.POST['clear'] = None
            for k in ['chosenspectra', 'chosenfasta']:
                if k in c:
                    del c[k]
            return searchpage(request, c=c)
        elif(request.POST.get('getstatus')):
            request.POST = request.POST.copy()
            request.POST['getstatus'] = None
            c['res_page'] = 1
            return status(request, c = c)
        elif(request.POST.get('search_runname')):
            request.POST = request.POST.copy()
            tmp_val = request.POST['search_button']
            request.POST['search_runname'] = None
            return status(request, c = c, search_run_filter=tmp_val)
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
        elif(request.POST.get('sendemail')):
            request.POST = request.POST.copy()
            request.POST['sendemail'] = None
            return email(request, c = c)
        elif(request.POST.get('uploadspectra')):
            request.POST = request.POST.copy()
            request.POST['uploadspectra'] = None
            return files_view_spectra(request, c = c)
        elif(request.POST.get('uploadfasta')):
            request.POST = request.POST.copy()
            request.POST['uploadfasta'] = None
            return files_view_fasta(request, c = c)
        elif(request.POST.get('uploadparams')):
            request.POST = request.POST.copy()
            request.POST['uploadparams'] = None
            return files_view_params(request, c = c)
        elif(request.POST.get('saveparams')):
            request.POST = request.POST.copy()
            if request.POST.get('paramsname'):
                # save_params(c['SearchParametersForm'], c['userid'], request.POST.get('paramsname'), c['paramtype'])
                save_params_new(c['SearchForms'], c['userid'], request.POST.get('paramsname'), c['paramtype'])
            request.POST['saveparams'] = None
            return searchpage(request, c = c)
        elif(request.POST.get('loadparams')):
            request.POST = request.POST.copy()
            request.POST['loadparams'] = None
            return files_view_params(request, c = c)
        elif(request.POST.get('add_protease')):
            request.POST = request.POST.copy()
            request.POST['add_protease'] = None
            return add_protease(request, c = c)
        elif(request.POST.get('sbm_protease')):
            request.POST = request.POST.copy()
            request.POST['sbm_protease'] = None
            return add_protease(request, c = c, sbm=True)
        elif(request.POST.get('del_protease')):
            request.POST = request.POST.copy()
            request.POST['del_protease'] = None
            return add_protease(request, c = c)
        elif(request.POST.get('add_modification')):
            request.POST = request.POST.copy()
            request.POST['add_modification'] = None
            return add_modification(request, c = c)
        elif(request.POST.get('select_fixed')):
            request.POST = request.POST.copy()
            request.POST['select_fixed'] = None
            return select_modifications(request, c = c, fixed=True)
        elif(request.POST.get('select_potential')):
            request.POST = request.POST.copy()
            request.POST['select_potential'] = None
            return select_modifications(request, c = c, fixed=False)
        elif(request.POST.get('sbm_mod')):
            request.POST = request.POST.copy()
            request.POST['sbm_mod'] = None
            return add_modification(request, c = c, sbm=True)
        elif(request.POST.get('search_details')):
            request.POST = request.POST.copy()
            return search_details(request, runname=request.POST['search_details'], c=c)
        elif(request.POST.get('show_proteins')):
            request.POST = request.POST.copy()
            request.POST['show_proteins'] = None
            return show(request, runname=request.POST['results_figure_actualname'], searchgroupid=request.POST['results_figure_searchgroupid'], c=c, ftype='protein')
        elif(request.POST.get('show_peptides')):
            request.POST = request.POST.copy()
            dbname = request.POST['show_peptides'] if not request.POST['show_peptides'].isdigit() else False
            request.POST['show_peptides'] = None
            return show(request, runname=request.POST['results_figure_actualname'], searchgroupid=request.POST['results_figure_searchgroupid'], c=c, ftype='peptide', dbname=dbname)
        elif(request.POST.get('show_psms')):
            request.POST = request.POST.copy()
            dbname = request.POST['show_psms'] if not request.POST['show_psms'].isdigit() else False
            request.POST['show_psms'] = None
            return show(request, runname=request.POST['results_figure_actualname'], searchgroupid=request.POST['results_figure_searchgroupid'], c=c, ftype='psm', dbname=dbname)
        elif(request.POST.get('order_by')):
            request.POST = request.POST.copy()
            order_column = request.POST['order_by']
            request.POST['order_by'] = None
            return show(request, runname=request.POST['results_figure_actualname'], searchgroupid=request.POST['results_figure_searchgroupid'], c=c, ftype=c['results_detailed'].ftype, order_by_label=order_column, upd=True)
        elif(request.POST.get('select_labels')):
            request.POST = request.POST.copy()
            request.POST['select_labels'] = None
            return show(request, runname=request.POST['results_figure_actualname'], searchgroupid=request.POST['results_figure_searchgroupid'], c=c, ftype=c['results_detailed'].ftype, upd=True)
        elif(request.POST.get('results_figure')):
            request.POST = request.POST.copy()
            return results_figure(request, runname=request.POST['results_figure_actualname'], searchgroupid=request.POST['results_figure_searchgroupid'], c=c)
        elif(request.POST.get('download_csv')):
            c['down_type'] = 'csv'
            return getfiles(c=c)
        elif(request.POST.get('download_pepxml')):
            c['down_type'] = 'pepxml'
            return getfiles(c=c)
        elif(request.POST.get('download_mgf')):
            c['down_type'] = 'mgf'
            return getfiles(c=c)
        elif(request.POST.get('download_figs')):
            c['down_type'] = 'figs'
            return getfiles(c=c)
        elif(request.POST.get('download_figs_svg')):
            c['down_type'] = 'figs_svg'
            return getfiles(c=c)
        elif(request.POST.get('prev_runs')):
            request.POST = request.POST.copy()
            request.POST['prev_runs'] = None
            c['res_page'] = c.get('res_page', 1) + 1
            return status(request, c=c)
        elif(request.POST.get('type1')):
            request.POST = request.POST.copy()
            request.POST['type1'] = None
            del c['SearchForms']
            c['paramtype'] = 1
            c = get_forms(request, c)
            return searchpage(request, c=c, upd=True)
        elif(request.POST.get('type2')):
            request.POST = request.POST.copy()
            request.POST['type2'] = None
            del c['SearchForms']
            c['paramtype'] = 2
            c = get_forms(request, c)
            return searchpage(request, c=c, upd=True)
        elif(request.POST.get('type3')):
            request.POST = request.POST.copy()
            request.POST['type3'] = None
            del c['SearchForms']
            c['paramtype'] = 3
            c = get_forms(request, c)
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
            if 'commonfiles' in request.FILES:
                for uploadedfile in request.FILES.getlist('commonfiles'):
                    fext = os.path.splitext(uploadedfile.name)[-1].lower()
                    if fext in ['.mgf', '.mzml']:
                        newdoc = SpectraFile(docfile = uploadedfile, user = request.user)
                        newdoc.save()
                    if fext == '.fasta':
                        newdoc = FastaFile(docfile = uploadedfile, user = request.user)
                        newdoc.save()
                    else:
                        pass
                messages.add_message(request, messages.INFO, 'Upload was done successfully')
                return HttpResponseRedirect(reverse('datasets:index'))
        else:
            commonform = CommonForm()

        if 'chosenparams' in c:
            os.remove(get_user_latest_params_path(c.get('paramtype', 3), c.get('userid', None)) )
            shutil.copy(c['chosenparams'][0].docfile.name.encode('ASCII'), get_user_latest_params_path(c.get('paramtype', 3), c.get('userid', None)) )
            # for chunk in c['chosenparams'].chunks():
            #     fd.write(chunk)
            # fd.close()

        c.update({'commonform': commonform})
        c['menubar'] = Menubar('about', request.user.is_authenticated())
        return render(request, 'datasets/index.html', c)
    else:
        c['menubar'] = Menubar('loginform', request.user.is_authenticated())
        return render(request, 'datasets/login.html', c)

def details(request, pK):
    doc = get_object_or_404(SpectraFile, id=pK)
    return render(request, 'datasets/details.html',
            {'document': doc})

def delete(request, c):
    usedclass=c['usedclass']
    usedname=c['usedname']
    documents = usedclass.objects.filter(user=request.user)
    cc = []
    for doc in documents:
        if not usedname == 'chosenparams' or not doc.name().startswith('latest_params'):
            cc.append((doc.id, doc.name()))
    form = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
    if form.is_valid():
        for x in form.cleaned_data.get('relates_to'):
            obj = c['usedclass'].objects.get(user=c['userid'], id=x)
            obj.delete()
    return searchpage(request, c)

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
        c['menubar'] = Menubar('contacts', request.user.is_authenticated())
        return contacts(request, c = {})
    if(request.POST.get('loginform')):
        request.POST = request.POST.copy()
        request.POST['loginform'] = None
        return loginview(request)
    if(request.POST.get('about')):
        request.POST = request.POST.copy()
        request.POST['about'] = None
        c['menubar'] = Menubar('about', request.user.is_authenticated())
        return about(request, c = {})
    elif(request.POST.get('sendemail')):
        request.POST = request.POST.copy()
        request.POST['sendemail'] = None
        c['menubar'] = Menubar('', request.user.is_authenticated())
        return email(request, c = c)
    c['menubar'] = Menubar('loginform', request.user.is_authenticated())
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
    elif(request.POST.get('sendemail')):
        request.POST = request.POST.copy()
        request.POST['sendemail'] = None
        return email(request, c = {})
    user = authenticate(username=request.POST['email'], password=request.POST['password'])
    if user is not None:
        request.session.set_expiry(24*60*60)
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


def status(request, c=dict(), search_run_filter=False):
    c = c
    c.update(csrf(request))
    res_page = c.get('res_page', 1)
    if search_run_filter:
        processes = SearchGroup.objects.filter(user=request.user.id, groupname__contains=search_run_filter).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
        c['res_page'] = 1
        c['max_res_page'] = int(math.ceil(float(SearchGroup.objects.filter(user=request.user.id, groupname__contains=search_run_filter).count()) / 10))
    else:
        c['max_res_page'] = int(math.ceil(float(SearchGroup.objects.filter(user=request.user.id).count()) / 10))
        processes = SearchGroup.objects.filter(user=request.user.id).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
    c.update({'processes': processes})
    c['menubar'] = Menubar('get_status', request.user.is_authenticated())
    return render(request, 'datasets/status.html', c)

def get_user_latest_params_path(paramtype, userid):
    return os.path.join('uploads', 'params', str(userid.id), 'latest_params_%d.cfg' % (paramtype, ))

def upload(request, c=dict()):
    c = c
    c.update(csrf(request))
    c['menubar'] = Menubar('upload', request.user.is_authenticated())
    return render(request, 'datasets/upload.html', c)

def searchpage(request, c=dict(), upd=False):
    c = c
    c.update(csrf(request))
    for sf in c['SearchForms'].values():
        c['SearchForms'][sf.sftype] = update_searchparams_form_new(request=request, paramtype=c['paramtype'], sftype=sf.sftype)
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)

    raw_config.read(get_user_latest_params_path(c.get('paramtype', 3), c['userid']) )
    c['menubar'] = Menubar('searchpage', request.user.is_authenticated())
    return render(request, 'datasets/startsearch.html', c)

def contacts(request,c=dict()):
    c=c
    c.update(csrf(request))
    c['menubar'] = Menubar('contacts', request.user.is_authenticated())
    return render(request, 'datasets/contacts.html', c)

def about(request,c=dict()):
    c=c
    c.update(csrf(request))
    c['menubar'] = Menubar('about', request.user.is_authenticated())
    return render(request, 'datasets/index.html', c)

def email(request, c={}):
    if all(z in request.POST.keys() for z in ['subject', 'from_email', 'message']):
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            from_email = form.cleaned_data['from_email']
            message = form.cleaned_data['message']
            messages.add_message(request, messages.INFO, 'Your message was sent to the developers. We will respond as soon as possible.')
            try:
                send_mail(subject, 'From %s\n' % (from_email, ) + message, from_email, ['markmipt@gmail.com'])
            except BadHeaderError:
                return HttpResponse('Invalid header found.')
            return contacts(request, c)
    else:
        form = ContactForm(initial={'from_email': request.user.username})
    return render(request, "datasets/email.html", {'form': form})

def add_modification(request, c=dict(), sbm=False):
    c = c
    c.update(csrf(request))
    if sbm:
        c['modificationform'] = AddModificationForm(request.POST)
        if c['modificationform'].is_valid():
            mod_name = c['modificationform'].cleaned_data['name']
            mod_label = c['modificationform'].cleaned_data['label']
            mod_mass = c['modificationform'].cleaned_data['mass']
            if c['modificationform'].cleaned_data['aminoacids'] == 'X':
                c['modificationform'].cleaned_data['aminoacids'] = parser.std_amino_acids
            added = []
            for aminoacid in c['modificationform'].cleaned_data['aminoacids']:
                if aminoacid in parser.std_amino_acids + ['[', ']']:
                    if not Modification.objects.filter(user=request.user, label=mod_label, mass=mod_mass, aminoacid=aminoacid).count():
                        modification_object = Modification(name=mod_name+aminoacid, label=mod_label, mass=mod_mass, aminoacid=aminoacid, user=request.user)
                        modification_object.save()
                        added.append(aminoacid)
            if added:
                messages.add_message(request, messages.INFO, 'A new modification was added')
                return searchpage(request, c)
            else:
                messages.add_message(request, messages.INFO, 'A modification with mass %f, label %s already exists for selected aminoacids' % (mod_mass, mod_label))
                return render(request, 'datasets/add_modification.html', c)
        else:
            messages.add_message(request, messages.INFO, 'All fields must be filled')
            return render(request, 'datasets/add_modification.html', c)
    c['modificationform'] = AddModificationForm()
    return render(request, 'datasets/add_modification.html', c)

def add_protease(request, c=dict(), sbm=False):
    c = c
    c.update(csrf(request))

    cc = []
    for pr in Protease.objects.all():
        cc.append((pr.id, '%s (rule: %s)' % (pr.name, pr.rule)))

    if request.POST.get('relates_to'):
        proteases = MultFilesForm(request.POST, custom_choices=cc, labelname='Delete proteases', multiform=True)
        if proteases.is_valid():
            for obj_id in proteases.cleaned_data.get('relates_to'):
                obj = Protease.objects.get(user=c['userid'], id=obj_id)
                obj.delete()
            request.POST['relates_to'] = False
        return add_protease(request, c, sbm=sbm)

    proteases = MultFilesForm(custom_choices=cc, labelname='Delete proteases', multiform=True)
    if sbm:
        c['proteaseform'] = AddProteaseForm(request.POST)
        if c['proteaseform'].is_valid():
            protease_name = c['proteaseform'].cleaned_data['name']
            if Protease.objects.filter(user=request.user, name=protease_name).count():
                messages.add_message(request, messages.INFO, 'Cleavage rule with name %s already exists' % (protease_name, ))
                return render(request, 'datasets/add_protease.html', c)
            try:
                protease_rule = utils.convert_tandem_cleave_rule_to_regexp(c['proteaseform'].cleaned_data['cleavage_rule'])
            except:
                messages.add_message(request, messages.INFO, 'Cleavage rule is incorrect')
                return render(request, 'datasets/add_protease.html', c)
            protease_order_val = Protease.objects.filter(user=request.user).aggregate(Max('order_val'))['order_val__max'] + 1
            protease_object = Protease(name=protease_name, rule=protease_rule, order_val=protease_order_val, user=request.user)
            protease_object.save()
            messages.add_message(request, messages.INFO, 'A new cleavage rule was added')
            return searchpage(request, c)
        else:
            messages.add_message(request, messages.INFO, 'All fields must be filled')
            return render(request, 'datasets/add_protease.html', c)
    c['proteaseform'] = AddProteaseForm()
    c['proteases'] = proteases
    return render(request, 'datasets/add_protease.html', c)

def select_modifications(request, c=dict(), fixed=True, upd=False):
    c = c
    c.update(csrf(request))
    modifications = Modification.objects.filter(user=request.user)
    cc = []
    for doc in modifications:
        cc.append((doc.id, '%s (label: %s, mass: %f, aminoacid: %s)' % (doc.name, doc.label, doc.mass, doc.aminoacid)))
    if upd:
        modform = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
        if modform.is_valid():
            chosenmodsids = [int(x) for x in modform.cleaned_data.get('relates_to')]
            chosenmods = Modification.objects.filter(id__in=chosenmodsids)
            save_mods(uid=request.user, chosenmods=chosenmods, fixed=fixed, paramtype=c['paramtype'])
            return searchpage(request, c)
    modform = MultFilesForm(custom_choices=cc, labelname='Select modifications', multiform=True)
    c.update({'usedclass': Modification, 'modform': modform, 'sbm_modform': True, 'fixed': fixed, 'select_form': 'modform', 'topbtn': (True if len(modform.fields.values()[0].choices) >= 15 else False)})
    return render(request, 'datasets/choose.html', c)

def files_view(request, usedclass=None, usedname=None, c=dict(), multiform=True):
    c = c
    c.update(csrf(request))
    if not usedclass or not usedname:
        usedclass=c['usedclass']
        usedname=c['usedname']
        del c['usedclass']
        del c['usedname']
    documents = usedclass.objects.filter(user=request.user)
    cc = []
    for doc in documents:
        if not usedname == 'chosenparams' or not doc.name().startswith('latest_params'):
            cc.append((doc.id, doc.name()))
    if request.POST.get('relates_to'):
        form = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
        if form.is_valid():
            chosenfilesids = [int(x) for x in form.cleaned_data.get('relates_to')]
            chosenfiles = usedclass.objects.filter(id__in=chosenfilesids)
            if usedname == 'chosenparams':
                paramfile = chosenfiles[0]
                dst = os.path.join(os.path.dirname(paramfile.docfile.name.encode('ASCII')), 'latest_params_3.cfg')
                shutil.copy(paramfile.docfile.name.encode('ASCII'), dst)
                c['paramtype'] = paramfile.type
                return searchpage(request, c, upd=True)
            else:
                c.update({usedname: chosenfiles})
                return searchpage(request, c)
    else:
        form = MultFilesForm(custom_choices=cc, labelname=None, multiform=multiform)
    c.update({'menubar': Menubar('choose', request.user.is_authenticated()), 'form': form, 'usedclass': usedclass, 'usedname': usedname, 'select_form': 'form', 'topbtn': (True if len(form.fields.values()[0].choices) >= 15 else False)})
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
    return files_view(request, usedclass, 'chosenparams', c = c, multiform=False)

def identiprot_view(request, c):
    c = runidentiprot(request, c)
    return status(request, c)

def runidentiprot(request, c):

    def run_search(newrun, rn, c):
        paramfile = newrun.parameters.all()[0].path()
        fastafile = newrun.fasta.all()[0].path()
        settings = main.settings(paramfile)
        settings.set('input', 'database', fastafile.encode('ASCII'))
        settings.set('output', 'path', 'results/%s/%s' % (str(newrun.user.id), rn.encode('ASCII')))
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
            ftype = os.path.splitext(tmpfile)[-1]
            if ftype in ['.png', '.svg'] and newrun.name() + '_' in os.path.basename(tmpfile):
                fl = open(os.path.join(dname, tmpfile))
                djangofl = File(fl)
                img = ResImageFile(docfile = djangofl, user = usr, ftype=ftype)
                img.save()
                newrun.add_resimage(img)
                fl.close()
        if os.path.exists(bname + '_PSMs.csv'):
            fl = open(bname + '_PSMs.csv')
            djangofl = File(fl)
            csvf = ResCSV(docfile = djangofl, user = usr, ftype='psm')
            csvf.save()
            newrun.add_rescsv(csvf)
        if os.path.exists(bname + '_peptides.csv'):
            fl = open(bname + '_peptides.csv')
            djangofl = File(fl)
            csvf = ResCSV(docfile = djangofl, user = usr, ftype='peptide')
            csvf.save()
            newrun.add_rescsv(csvf)
        if os.path.exists(bname + '_proteins.csv'):
            fl = open(bname + '_proteins.csv')
            djangofl = File(fl)
            csvf = ResCSV(docfile = djangofl, user = usr, ftype='protein')
            csvf.save()
            newrun.add_rescsv(csvf)
        newrun.calc_results()
        return 1

    def runproc(inputfile, settings, newrun, usr):
        filename = set_pepxml_path(settings, inputfile)
        utils.write_pepxml(inputfile, settings, main.process_file(inputfile, settings))
        fl = open(filename, 'r')
        djangofl = File(fl)
        pepxmlfile = PepXMLFile(docfile = djangofl, user = usr)
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

    if not os.path.exists('results'):
        os.mkdir('results')
    if not os.path.exists(os.path.join('results', str(c['userid'].id))):
        os.mkdir(os.path.join('results', str(c['userid'].id)))
    if not os.path.exists('results/%s/%s' % (str(c['userid'].id), c['runname'])):
        newgroup = SearchGroup(groupname=c['runname'], user = c['userid'])
        newgroup.save()
        newgroup.add_files(c)
        rn = newgroup.name()
        os.mkdir('results/%s/%s' % (str(newgroup.user.id), rn.encode('ASCII')))
        newgroup.change_status('Search is running')
        p = Process(target=start_all, args=(newgroup, rn, c))
        p.start()
        messages.add_message(request, messages.INFO, 'Identiprot started')
    else:
        messages.add_message(request, messages.INFO, 'Results with name %s already exist, choose another name' % (c['runname'], ))
    return c


def search_details(request, runname, c=dict()):
    c = c
    c.update(csrf(request))
    runobj = SearchGroup.objects.get(groupname=runname.replace(u'\xa0', ' '))
    c.update({'searchgroup': runobj})
    return render(request, 'datasets/results.html', c)

def results_figure(request, runname, searchgroupid, c=dict()):
    c = c
    c.update(csrf(request))
    runobj = get_object_or_404(SearchRun, runname=runname.replace(u'\xa0', ' '), searchgroup_parent_id=searchgroupid)
    c.update({'searchrun': runobj})
    return render(request, 'datasets/results_figure.html', c)


def show(request, runname, searchgroupid, ftype, c=dict(), order_by_label=False, upd=False, dbname=False):
    c = c
    c.update(csrf(request))
    if not upd:
        runobj = SearchRun.objects.get(runname=runname.replace(u'\xa0', ' '), searchgroup_parent_id=searchgroupid)
        res_dict = runobj.get_detailed(ftype=ftype)
    else:
        res_dict = c['results_detailed']
    if order_by_label:
        res_dict.custom_order(order_by_label)
    if dbname:
        res_dict.filter_dbname(dbname)
    labelname = 'Select columns for %ss' % (ftype, )
    if request.POST.get('relates_to'):
        res_dict.labelform = MultFilesForm(request.POST, custom_choices=zip(res_dict.labels, res_dict.labels), labelname=labelname, multiform=True)
        if res_dict.labelform.is_valid():
            whitelabels = [x for x in res_dict.labelform.cleaned_data.get('relates_to')]
            res_dict.custom_labels(whitelabels)
            request.POST['relates_to'] = False
    else:
        res_dict.labelform = MultFilesForm(custom_choices=zip(res_dict.labels, res_dict.labels), labelname=labelname, multiform=True)
    c.update({'results_detailed': res_dict})
    return render(request, 'datasets/results_detailed.html', c)

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
        elif c['down_type'] == 'figs_svg':
            for down_fn in searchrun.get_resimage_paths(ftype='.svg'):
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
