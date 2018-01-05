# -*- coding: utf-8 -*-
import django
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core.files import File
from django.core.mail import send_mail, BadHeaderError
from django.contrib import messages
from django.db.models import Max, Min, Sum
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
import django.db

from django.conf import settings
import os
import subprocess
import zipfile
import StringIO
import shutil
import math
from copy import copy
import tempfile
import time
import random
import pickle
import sys
from multiprocessing import Process
from threading import Thread
import urllib
import urlparse
import glob
import gzip
import zipfile
import logging
logger = logging.getLogger(__name__)

from pyteomics import parser, mass
os.chdir(settings.BASE_DIR)
sys.path.insert(0, '../identipy/')
sys.path.insert(0, '../mp-score/')
from identipy import main, utils
import MPscore

from .aux import save_mods, save_params_new, ResultsDetailed, get_size
from .models import SpectraFile, RawFile, FastaFile, ParamsFile, PepXMLFile, ResImageFile, ResCSV
from .models import SearchGroup, SearchRun, Protease, Modification 
from .models import upload_to_basic
from . import forms

RUN_LIMIT = getattr(settings, 'NUMBER_OF_PARALLEL_RUNS', 1)

try:
    runs = SearchRun.objects.exclude(status=SearchRun.FINISHED).exclude(status=SearchRun.DEAD)
    for r in runs:
        r.status = SearchRun.DEAD
        r.save()
        logger.info('Reaping run %s from %s by %s', r.id, r.searchgroup.groupname, r.searchgroup.user.username)
except Exception as e:
    logger.warning('Startup cleanup failed.\n%s', e)


def add_forms(request, c):
    c['paramtype'] = c.get('paramtype')
    if not c['paramtype']:
        c['paramtype'] = request.session.setdefault('paramtype', 3)
    request.session['paramtype'] = c['paramtype']
    c['SearchForms'] = forms.search_forms_from_request(request)

def form_dispatch(request):
    c = {}
    if request.GET or not request.user.is_authenticated():
        return redirect('identipy_app:index')
    action = request.POST['submit_action']
    if action != 'Search previous runs by name':
        sforms = forms.search_forms_from_request(request)
        sessiontype = request.session.get('paramtype')
        save_params_new(sforms, request.user, False, sessiontype)
    redirect_map = {
            'Select spectra': ('identipy_app:choose', 'spectra'),
            'Select protein database': ('identipy_app:choose', 'fasta'),
            'select fixed modifications': ('identipy_app:choose', 'fmods'),
            'select potential modifications': ('identipy_app:choose', 'vmods'),
            'enzyme': ('identipy_app:new_protease',),
            'RUN IdentiPy': ('identipy_app:run',),
            'save parameters': ('identipy_app:save',),
            'load parameters': ('identipy_app:choose', 'params'),
            'Search previous runs by name': ('identipy_app:getstatus', request.POST.get('search_button')),
            'Minimal': ('identipy_app:searchpage',),
            'Medium': ('identipy_app:searchpage',),
            'Advanced': ('identipy_app:searchpage',),
            }

    request.session['redirect'] = redirect_map[action]
    request.session['runname'] = request.POST.get('runname')
    request.session['paramsname'] = request.POST.get('paramsname')
    if action in {'Minimal', 'Medium', 'Advanced'}:
        gettype = {'Minimal': 1, 'Medium': 2, 'Advanced': 3}[action]
        if sessiontype != gettype:
            if sforms is not None:
                request.session['paramtype'] = gettype
                newforms = forms.search_forms_from_request(request, ignore_post=True)
        request.session['paramtype'] = c['paramtype'] = gettype

    return redirect(*redirect_map[action])

def save_parameters(request):
    sforms = forms.search_forms_from_request(request, ignore_post=True)
    save_params_new(sforms, request.user, request.session.get('paramsname'), request.session.get('paramtype', 3))
    messages.add_message(request, messages.INFO, 'Parameters saved.')
    return redirect('identipy_app:searchpage')

def index(request):
    # TODO: fix the double "if logged in" logic
    if request.user.is_authenticated():
        return redirect('identipy_app:searchpage')
    else:
        return redirect('identipy_app:loginform')

def details(request, pK):
    doc = get_object_or_404(SpectraFile, id=pK)
    return render(request, 'identipy_app/details.html', {'document': doc})

def delete(request, usedclass):
    usedname=usedclass.__name__
    documents = usedclass.objects.filter(user=request.user)
    cc = []
    for doc in documents:
        if not usedname == 'ParamsFile' or not doc.name().startswith('latest_params'):
            try:
                cc.append((doc.id, doc.name()))
            except:
                cc.append((doc.id, doc.name))
    form = forms.MultFilesForm(request.POST, custom_choices=cc, labelname=None)
    if form.is_valid():
        for x in form.cleaned_data.get('choices'):
            obj = usedclass.objects.get(user=request.user, id=x)
            try:
                obj.customdel()
            except:
                obj.delete()

    return redirect(*request.session['redirect'])

def logout_view(request):
    logout(request)
    return redirect('identipy_app:index')

def loginview(request):
    c = {}
    c['message'] = request.session.get('message')

    c['current'] = 'loginform'
    return render(request, 'identipy_app/login.html', c)

def auth_and_login(request, onsuccess='identipy_app:index', onfail='identipy_app:loginform'):
    user = authenticate(username=request.POST['login'], password=request.POST['password'])
    if user is not None:
        request.session.set_expiry(24*60*60)
        login(request, user)
        messages.add_message(request, messages.INFO, 'Login successful.')
        return redirect(onsuccess)
    else:
        request.session['message'] = 'Wrong username or password'
        return redirect(onfail)


def delete_search(request):
    for name, val in request.POST.iteritems():
        if val == u'on':
            processes = SearchGroup.objects.filter(user=request.user.id, groupname=name.replace(u'\xa0', ' '))
            for obj in processes:
                obj.full_delete()
    return redirect('identipy_app:getstatus')

def status(request, name_filter=False):
    logger.debug('Status page requested by %s', request.user)
    c = {}
    request.session.setdefault('res_page', 1)
    if request.method == 'GET':
        request.session['res_page'] += int(request.GET.get('res_page', 0))
        request.session['res_page'] = max(1, request.session['res_page'])
    res_page = request.session.get('res_page', 1)
    if name_filter:
        nf = urllib.unquote_plus(name_filter)
        request.session['name filter'] = nf
    else:
        nf = request.session.get('name_filter', False)
    c.setdefault('search_run_filter', nf)
    if c['search_run_filter']:
        c['max_res_page'] = int(math.ceil(float(SearchGroup.objects.filter(user=request.user.id, groupname__contains=c['search_run_filter']).count()) / 10))
        res_page = min(res_page, c['max_res_page'])
        processes = SearchGroup.objects.filter(user=request.user.id, groupname__contains=c['search_run_filter']).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
    else:
        c['max_res_page'] = int(math.ceil(float(SearchGroup.objects.filter(user=request.user.id).count()) / 10))
        res_page = min(res_page, c['max_res_page'])
        processes = SearchGroup.objects.filter(user=request.user.id).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
    request.session['res_page'] = res_page
    c.setdefault('res_page', res_page)
    c.update({'processes': processes})
    c['current'] = 'get_status'
    return render(request, 'identipy_app/status.html', c)


def _save_uploaded_file(uploadedfile, user):
    if isinstance(uploadedfile, basestring):
        fname = uploadedfile
    else:
        fname = uploadedfile.name
    name, fext = os.path.splitext(fname.lower())
    if fext == '.gz':
        name, fext = os.path.splitext(name)
    logger.debug('Determined extension: %s', fext)
    if fext in {'.mgf', '.mzml'}:
        newdoc = SpectraFile(docfile=uploadedfile, user=user)
        newdoc.save()
    elif fext in {'.fasta', '.faa'}:
        newdoc = FastaFile(docfile=uploadedfile, user=user)
        newdoc.save()
    else:
        logging.error('Unsupported file uploaded: %s', uploadedfile)

def upload(request):
    c = {}
    c['current'] = 'upload'
    c['system_size'] = get_size(os.path.join('results', str(request.user.id)))
    for dirn in ['spectra', 'fasta', 'params']:
        c['system_size'] += get_size(os.path.join('uploads', dirn, str(request.user.id)))
    c['LOCAL_IMPORT'] = getattr(settings, 'LOCAL_IMPORT', False)
    c['URL_IMPORT'] = getattr(settings, 'URL_IMPORT', False)

    # Handle file upload
    if request.method == 'POST':
        commonform = forms.CommonForm(request.POST, request.FILES)
        if 'commonfiles' in request.FILES:
            for uploadedfile in request.FILES.getlist('commonfiles'):
                z, ret = _dispatch_file_handling(uploadedfile, request.user)
                if z:
                    d, outs = ret
                    for _, files in outs:
                        fname, path, opener = files
                        with opener(fname) as f:
                            _copy_in_chunks(f, path)
                        _save_uploaded_file(path, request.user)
                    shutil.rmtree(d)
                else:
                    fname, path, opener = ret
                    if fname[-3:] == '.gz':
                        with gzip.GzipFile(fileobj=uploadedfile, mode='rb') as f:
                            _copy_in_chunks(f, path)
                        _save_uploaded_file(path, request.user)
                    else:
                        _save_uploaded_file(uploadedfile, request.user)
            messages.add_message(request, messages.INFO, 'Upload successful.')
            next = request.session.get('next', [])
            if next:
                return redirect(*next.pop())
        else:
            messages.add_message(request, messages.INFO, 'Choose files for upload.')
    else:
        commonform = forms.CommonForm()
        li_form = forms.LocalImportForm()
        c['localimportform'] = li_form

    c['commonform'] = commonform
    return render(request, 'identipy_app/upload.html', c)

def _dispatch_file_handling(f, user, opener=None, fext=None):
    if isinstance(f, basestring):
        fname = f
    else:
        fname = f.name
    fext = fext or os.path.splitext(fname)[-1][1:].lower()
    if fext == 'gz':
        fext = os.path.splitext(os.path.splitext(fname)[0])[1][1:].lower()
        return _dispatch_file_handling(fname, user, lambda x: gzip.open(x, 'rb'), fext)
    if fext == 'zip':
        tmpdir = tempfile.mkdtemp()
        with tempfile.NamedTemporaryFile() as tmpf:
            _copy_in_chunks(f, tmpf.name)
            zf = zipfile.ZipFile(tmpf)
            zf.extractall(tmpdir)
        rets = [
                _dispatch_file_handling(os.path.join(dirpath, f), user)
                for dirpath, dirs, fs in os.walk(tmpdir)
                for f in fs
                ]
        zf.close()
        return True, (tmpdir, rets)
    try:
        dirn = {'mgf': 'spectra', 'mzml': 'spectra', 'fasta': 'fasta', 'faa': 'fasta', 'cfg': 'params'}[fext]
    except KeyError as ke:
        return ke.args[0]
    path = upload_to_basic(dirn, os.path.split(fname)[1], user.id)
    name, ext = os.path.splitext(path)
    if ext == '.gz':
        path = name
    logger.debug('Copying to %s', path)
    if opener is None: opener = lambda f: open(f, 'rb')
    return False, (fname, path, opener)

def _dispatch_and_copy(fname, user, opener=None):
    z, ret = _dispatch_file_handling(fname, user)
    if z:
        d, rets = ret
        out = []
        for r in rets:
            out.append(_copy_in_chunks(*r))
        shutil.rmtree(d)
        return out
    fname, path, opener = ret
    with opener(fname) as f:
        return _copy_in_chunks(f, path)

def _copy_in_chunks(f, path):
    try:
        with open(path, 'wb') as ff:
            while True:
                chunk = f.read(5*1024*1024)
                if chunk:
                    ff.write(chunk)
                else:
                    break
    except IOError as e:
        logger.error('Error importing %s: %s', f.name, e.args)
    else:
        return path


def _local_import(fname, user, link=False):
    logger.info('IMPORTING FILE: %s', fname)
    fext = os.path.splitext(fname)[-1][1:].lower()
    if fext == 'zip':
        tmpdir = tempfile.mkdtemp()
        logger.debug('Extracting to %s', tmpdir)
        zf = zipfile.ZipFile(fname)
        zf.extractall(tmpdir)
        rets = [
                _dispatch_file_handling(os.path.join(dirpath, f), user)
                for dirpath, dirs, fs in os.walk(tmpdir)
                for f in fs
                ]
        zf.close()
        for _, out in rets:
            f, path, opener = out
            shutil.copy(f, path)
            _save_uploaded_file(path, user)
        shutil.rmtree(tmpdir)
    else:
        z, out = _dispatch_file_handling(fname, user)
        fname, path, opener = out
        if not link:
            with opener(fname) as f:
                _copy_in_chunks(f, path)
        else:
            logger.debug('Creating symlink: %s -> %s', path, fname)
            os.symlink(fname, path)
        _save_uploaded_file(path, user)

def _local_import_worker(request):
    fname = request.POST.get('filePath')
    link = request.POST.get('link')
    ret = []
    if os.path.isdir(fname):
        for root, dirs, files in os.walk(fname):
            for f in files:
                ret.append(_local_import(os.path.join(root, f), request.user, link))
    else:
        for f in glob.glob(fname):
            ret.append(_local_import(f, request.user, link))
    n = sum(r is None for r in ret)
    message = '{} file(s) imported.'.format(n)
    messages.add_message(request, messages.INFO, message)
    django.db.connection.close()

def local_import(request):
    if request.method == 'POST':
        fname = request.POST.get('filePath')
        link = request.POST.get('link')
        if os.path.isfile(fname):
            ret = _local_import(fname, request.user, link)
            if ret is None:
                message = 'Import successful.'
            else:
                message = 'Unsupported file extension: {}'.format(ret)
            messages.add_message(request, messages.INFO, message)
        else:
            t = Thread(target=_local_import_worker, args=(request,), name='local-import')
            t.start()
            messages.info(request, 'Local import started.')
        next = request.session.get('next', [])
        if next:
            return redirect(*next.pop())

    return redirect('identipy_app:upload')

def _url_import_worker(request):
    fname = request.POST.get('fileUrl')
    parsed = urlparse.urlparse(fname)
    local_name = os.path.split(parsed.path)[1]
    tmpfile = os.path.join(tempfile.gettempdir(), local_name)
    logger.info('Downloading %s ...', fname)
    urllib.urlretrieve(fname, tmpfile)
    logger.info('Saved to %s', tmpfile)
    _local_import(tmpfile, request.user)
    os.remove(tmpfile)
    messages.add_message(request, messages.INFO, 'Download successful.')
    django.db.connection.close()


def url_import(request):
    if request.method == 'POST':
        t = Thread(target=_url_import_worker, args=(request,), name='url-import')
        t.start()
        messages.info(request, 'Download started.')
        next = request.session.get('next', [])
        if next:
            return redirect(*next.pop())
    return redirect('identipy_app:upload')

def searchpage(request):
    c = {}

    c['paramtype'] = request.session.setdefault('paramtype', 3)
    add_forms(request, c)
    c['current'] = 'searchpage'
    for key, klass in zip(['spectra', 'fasta'], [SpectraFile, FastaFile]):
        c['chosen' + key] = klass.objects.filter(id__in=request.session.get('chosen_' + key, []))
    return render(request, 'identipy_app/startsearch.html', c)

def contacts(request):
    c = {}
    c['current'] = 'contacts'
    return render(request, 'identipy_app/contacts.html', c)

def about(request):
    c = {}
    c['current'] = 'about'
    return render(request, 'identipy_app/about.html', c)

def email(request):
    c = {}
    if all(z in request.POST.keys() for z in ['subject', 'message']):
        form = forms.ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            from_email = request.user.email
            message = form.cleaned_data['message']
            messages.add_message(request, messages.INFO, 'Your message was sent to the developers. We will respond as soon as possible.')
            try:
                send_mail(subject, 'From %s\n' % (from_email, ) + message, from_email, settings.EMAIL_SEND_TO)
            except BadHeaderError:
                return HttpResponse('Invalid header found.')
            except Exception as e:
                logger.error('Could not send email to developers:\n%s', e)
            return redirect('identipy_app:contacts')
    else:
        form = forms.ContactForm(initial={'from_email': request.user.username})
    return render(request, "identipy_app/email.html", {'form': form})


def email_to_user(username, searchname):
    try:
        send_mail('IdentiPy Server notification', 'Search %s was finished' % (searchname, ), 'identipymail@gmail.com', [username, ])
    except Exception as e:
        logger.error('Could not send email to user %s about run %s:\n%s', username, searchname, e)


def add_modification(request):
    c = {}
    if request.method == 'POST':
        c['modificationform'] = forms.AddModificationForm(request.POST)
        if c['modificationform'].is_valid():
            mod_name = c['modificationform'].cleaned_data['name']
            mod_label = c['modificationform'].cleaned_data['label'].lower()
            mod_mass = str(c['modificationform'].cleaned_data['mass'])
            try:
                mod_mass = float(mod_mass)
            except:
                try:
                    mod_mass = mass.calculate_mass(mass.Composition(mod_mass))
                except:
                    messages.add_message(request, messages.INFO, 'Invalid modification mass. Examples: 12.345 or -67.89 or C2H6O1 or N-1H-3')
                    return render(request, 'identipy_app/add_modification.html', c)
            if c['modificationform'].cleaned_data['aminoacids'] == 'X':
                c['modificationform'].cleaned_data['aminoacids'] = parser.std_amino_acids
            added = []
            allowed_set = set(list(mass.std_aa_mass) + ['[', ']'])
            for aminoacid in c['modificationform'].cleaned_data['aminoacids'].split(','):
                if (len(aminoacid) == 1 and aminoacid in allowed_set) \
                        or (len(aminoacid) == 2 and ((aminoacid[0]=='[' and aminoacid[1] in allowed_set) or (aminoacid[1]==']' and aminoacid[0] in allowed_set))):
                    if not Modification.objects.filter(user=request.user, label=mod_label, mass=mod_mass, aminoacid=aminoacid).count():
                        modification_object = Modification(name=mod_name+aminoacid, label=mod_label, mass=mod_mass, aminoacid=aminoacid, user=request.user)
                        modification_object.save()
                        added.append(aminoacid)
                    else:
                        messages.add_message(request, messages.INFO, 'A modification with mass %f, label %s already exists for selected aminoacids' % (mod_mass, mod_label))
                        return render(request, 'identipy_app/add_modification.html', c)
            if not added:
                messages.add_message(request, messages.INFO, 'Unknown aminoacid')
                return render(request, 'identipy_app/add_modification.html', c)
            else:
                messages.add_message(request, messages.INFO, 'A new modification was added')
                if 'next' in request.session:
                    logger.debug('Session next: %s', request.session['next'])
                    return redirect(*request.session['next'].pop())
                else:
                    return redirect('identipy_app:searchpage')
        else:
            messages.add_message(request, messages.INFO, 'All fields must be filled')
            return render(request, 'identipy_app/add_modification.html', c)
    else:
        c['modificationform'] = forms.AddModificationForm()
        return render(request, 'identipy_app/add_modification.html', c)

def add_protease(request):
    c = {}
    cc = []
    for pr in Protease.objects.filter(user=request.user):
        cc.append((pr.id, '%s (rule: %s)' % (pr.name, pr.rule)))

    if request.POST.get('submit_action', '') == 'delete':
        if request.POST.get('choices'):
            proteases = forms.MultFilesForm(request.POST, custom_choices=cc, labelname='proteases', multiform=True)
            if proteases.is_valid():
                for obj_id in proteases.cleaned_data.get('choices'):
                    obj = Protease.objects.get(user=request.user, id=obj_id)
                    obj.delete()
        cc = []
        for pr in Protease.objects.filter(user=request.user):
            cc.append((pr.id, '%s (rule: %s)' % (pr.name, pr.rule)))
        proteases = forms.MultFilesForm(custom_choices=cc, labelname='proteases', multiform=True)
        c['proteaseform'] = forms.AddProteaseForm()
        c['proteases'] = proteases
        return render(request, 'identipy_app/add_protease.html', c)

    proteases = forms.MultFilesForm(custom_choices=cc, labelname='proteases', multiform=True)
    if request.method == 'POST':
        c['proteaseform'] = forms.AddProteaseForm(request.POST)
        if c['proteaseform'].is_valid():
            protease_name = c['proteaseform'].cleaned_data['name']
            if Protease.objects.filter(user=request.user, name=protease_name).count():
                messages.add_message(request, messages.INFO, 'Cleavage rule with name %s already exists' % (protease_name, ))
                return render(request, 'identipy_app/add_protease.html', c)
            try:
                protease_rule = c['proteaseform'].cleaned_data['cleavage_rule']
            except:
                messages.add_message(request, messages.INFO, 'Cleavage rule is incorrect')
                return render(request, 'identipy_app/add_protease.html', c)
            protease_order_val = Protease.objects.filter(user=request.user).aggregate(Max('order_val'))['order_val__max'] + 1
            protease_object = Protease(name=protease_name, rule=protease_rule, order_val=protease_order_val, user=request.user)
            protease_object.save()
            messages.add_message(request, messages.INFO, 'A new cleavage rule was added')
            sforms = forms.search_forms_from_request(request, ignore_post=True)
            e = sforms['main'].fields['enzyme']
            proteases = Protease.objects.filter(user=request.user).order_by('order_val')
            choices = [(p.rule, p.name) for p in proteases]
            e.choices = choices
            save_params_new(sforms, request.user, False, request.session['paramtype'])
            return redirect('identipy_app:searchpage')
        else:
            messages.add_message(request, messages.INFO, 'All fields must be filled')
            return render(request, 'identipy_app/add_protease.html', c)
    else:
        c['proteaseform'] = forms.AddProteaseForm()
        c['proteases'] = proteases
        return render(request, 'identipy_app/add_protease.html', c)

def files_view(request, what):
    what_orig = what
    if what == 'fmods':
        what = 'mods'
        fixed = True
    elif what == 'vmods':
        what = 'mods'
        fixed = False

    usedclass = {'spectra': SpectraFile, 'fasta': FastaFile, 'params': ParamsFile,
            'mods': Modification}[what]
    c = {}
    multiform = (usedclass in {SpectraFile, Modification})
    documents = usedclass.objects.filter(user=request.user)
    choices = []
    for doc in documents:
        if what == 'mods':
            if not fixed or (not doc.aminoacid.count('[') and not doc.aminoacid.count(']')):
                choices.append((doc.id, '%s (label: %s, mass: %f, aminoacid: %s)' % (doc.name, doc.label, doc.mass, doc.aminoacid)))
        elif what in {'spectra', 'fasta'}:
            choices.append((doc.id, doc.name()))
        elif what == 'params' and (not doc.name().startswith('latest_params') and doc.visible):
            choices.append((doc.id, doc.title or doc.name()))
    if request.method == 'POST':
        action = request.POST['submit_action']
        if action == 'upload new files':
            request.session.setdefault('next', []).append(('identipy_app:choose', what_orig))
            return redirect('identipy_app:upload')
        elif action == 'add custom modification':
            request.session.setdefault('next', []).append(('identipy_app:choose', what_orig))
            return redirect('identipy_app:new_mod')
        elif action == 'download':
            return getfiles(request, usedclass=usedclass)
        elif action == 'delete':
            return delete(request, usedclass=usedclass)

        form = forms.MultFilesForm(request.POST, custom_choices=choices)
        if form.is_valid():
            chosenfilesids = [int(x) for x in form.cleaned_data['choices']]
            chosenfiles = usedclass.objects.filter(id__in=chosenfilesids)
            sforms = forms.search_forms_from_request(request, ignore_post=True)
            if what == 'mods':
                save_mods(uid=request.user, chosenmods=chosenfiles, fixed=fixed, paramtype=request.session['paramtype'])
                key = 'fixed' if fixed else 'variable' 
                sforms['main'][key].initial = ','.join(mod.get_label() for mod in chosenfiles)
                save_params_new(sforms, request.user, False, request.session['paramtype'])
            if what == 'params':
                paramfile = chosenfiles[0]
                parname = paramfile.docfile.name
                dst = os.path.join(os.path.dirname(parname), 'latest_params_%s.cfg' % (paramfile.type))
                logger.debug('Copy: %s -> %s', parname, dst)
                shutil.copy(parname, dst)
                request.session['paramtype'] = paramfile.type
#               save_params_new(sforms, request.user, False, request.session['paramtype'])
            else:
                request.session['chosen_' + what] = chosenfilesids
            return redirect('identipy_app:searchpage')
    else:
        kwargs = dict(custom_choices=choices, multiform=multiform)
        if what == 'mods':
            kwargs['labelname'] = 'Select {} modifications:'.format('fixed' if fixed else 'variable')
        form = forms.MultFilesForm(**kwargs)
        if what == 'mods' and not fixed:
            initvals = [mod.id for mod in Modification.objects.filter(name__in=['ammoniumlossC', 'ammoniumlossQ', 'waterlossE'])]
            form.fields['choices'].initial = initvals

    c.update({'form': form, 'used_class': what})
    return render(request, 'identipy_app/choose.html', c)

def _run_search(request, newrun, rn, c):
    django.db.connection.ensure_connection()
    sg = newrun.searchgroup
    paramfile = sg.parameters.path()
    fastafile = sg.fasta.all()[0].path()
    idsettings = main.settings(paramfile)
    enz = idsettings.get('search', 'enzyme')
    protease = Protease.objects.filter(user=request.user, name=enz).first()
    idsettings.set('search', 'enzyme', protease.rule + '|' + idsettings.get_choices('search', 'enzyme'))
    idsettings.set('misc', 'iterate', 'peptides')
    idsettings.set('input', 'database', fastafile)
    idsettings.set('output', 'path', 'results/%s/%s' % (str(newrun.searchgroup.user.id), newrun.searchgroup.id))
    _totalrun(request, idsettings, newrun, paramfile)
    if _exists(newrun):
        newrun.status = SearchRun.FINISHED
        newrun.save()
    else:
        logger.warning('Run %s appears to have been killed. Exiting run-search', newrun.id)
    django.db.connection.close()

def _set_pepxml_path(idsettings, inputfile):
    if idsettings.has_option('output', 'path'):
        outpath = idsettings.get('output', 'path')
    else:
        outpath = os.path.dirname(inputfile)
    return os.path.join(outpath, os.path.splitext(
        os.path.basename(inputfile))[0] + os.path.extsep + 'pep' + os.path.extsep + 'xml')


def _exists(run):
    time.sleep(2)
    if not SearchRun.objects.filter(pk=run.pk).exists():
        logger.info('The SearchRun object %s has been deleted, exiting ...', run.pk)
        return False
    return True


def _totalrun(request, idsettings, newrun, paramfile):
    spectralist = newrun.get_spectrafiles_paths()
    fastalist = newrun.get_fastafile_path()
    if not newrun.union:
        inputfile = newrun.spectra.path()
        p = Process(target=_runproc, args=(inputfile, idsettings))
        p.start()
        newrun.processpid = p.pid
        newrun.save()
        p.join()
    
        filename = _set_pepxml_path(idsettings, inputfile)

        # check if run has been killed
        if not _exists(newrun):
            logger.debug('Abandoning killed run %s ...', newrun.pk)
            return

        with open(filename, 'rb') as fl:
            djangofl = File(fl)
            pepxmlfile = PepXMLFile(docfile=djangofl, user=request.user, run=newrun)
            pepxmlfile.docfile.name = filename
            pepxmlfile.save()
        pepxmllist = newrun.get_pepxmlfiles_paths()
        paramlist = [paramfile]
        bname = pepxmllist[0].split('.pep.xml')[0]

    else:
        pepxmllist = newrun.get_pepxmlfiles_paths()
        paramlist = [paramfile]
        bname = os.path.join(os.path.dirname(pepxmllist[0]), 'union')

    if not _exists(newrun):
        return
    MPscore.main(['_'] + pepxmllist + spectralist + fastalist + paramlist, union_custom=newrun.union)
    if not os.path.isfile(bname + '_PSMs.csv'):
        bname = os.path.dirname(bname) + '/union'

    if not _exists(newrun):
        return
    dname = os.path.dirname(pepxmllist[0])
    for tmpfile in os.listdir(dname):
        ftype = os.path.splitext(tmpfile)[-1]
        if ftype in {'.png', '.svg'} and newrun.name() + '_' in os.path.basename(tmpfile):
            fl = open(os.path.join(dname, tmpfile))
            djangofl = File(fl)
            img = ResImageFile(docfile=djangofl, user=request.user, ftype=ftype, run=newrun)
            img.save()
            fl.close()
    if os.path.exists(bname + '_PSMs.csv'):
        fl = open(bname + '_PSMs.csv')
        djangofl = File(fl)
        csvf = ResCSV(docfile=djangofl, user=request.user, ftype='psm', run=newrun)
        csvf.save()
    if os.path.exists(bname + '_PSMs.pep.xml'):
        fl = open(bname + '_PSMs.pep.xml', 'rb')
        djangofl = File(fl)
        pepxmlfile = PepXMLFile(docfile=djangofl, user=request.user, filtered=True, run=newrun)
        pepxmlfile.docfile.name = bname + '_PSMs.pep.xml'
        pepxmlfile.save()
    if os.path.exists(bname + '_peptides.csv'):
        fl = open(bname + '_peptides.csv')
        djangofl = File(fl)
        csvf = ResCSV(docfile=djangofl, user=request.user, ftype='peptide', run=newrun)
        csvf.save()
    if os.path.exists(bname + '_proteins.csv'):
        fl = open(bname + '_proteins.csv')
        djangofl = File(fl)
        csvf = ResCSV(docfile=djangofl, user=request.user, ftype='protein', run=newrun)
        csvf.save()
    for pxml in newrun.get_pepxmlfiles():
        full = pxml.docfile.name.rsplit('.pep.xml', 1)[0] + '_full.pep.xml'
        shutil.move(pxml.docfile.name, full)
        pxml.docfile.name = full
        pxml.save()
    newrun.calc_results()
    django.db.connection.close()

def _runproc(inputfile, idsettings):
    utils.write_pepxml(inputfile, idsettings, main.process_file(inputfile, idsettings))

def _start_union(request, newgroup, rn, c):
    django.db.connection.ensure_connection()
    try:
        un_run = newgroup.get_union()
    except:
        un_run = False
    if un_run:
        _run_search(request, un_run, rn, c)

    if newgroup.notification:
        email_to_user(newgroup.user.email, newgroup.groupname)
    django.db.connection.close()

def _start_all(request, newgroup, rn, c):
    django.db.connection.ensure_connection()

    tmp_procs = []
    for newrun in newgroup.get_searchruns():
        while True:
            running = SearchRun.objects.filter(status=SearchRun.RUNNING)
            logger.debug('%s runs currently running', len(running))
            if len(running) == 0:
                logger.debug('Server idle, starting right away ...')
                break
            elif len(running) >= RUN_LIMIT:
                logger.debug('Too many active runs, waiting ...')
                pass
            else:
                last_user = running.latest('last_update').searchgroup.user
                logger.debug('Last user: %s', last_user.username)
                try:
                    next_user = SearchRun.objects.filter(status=SearchRun.WAITING).exclude(
                            searchgroup__user=last_user).earliest('last_update').searchgroup.user
                except SearchRun.DoesNotExist:
                    logger.debug('No competing users, starting ...')
                    break
                else:
                    logger.debug('Next user: %s', next_user)
                    if next_user == newrun.searchgroup.user:
                        logger.debug('My turn has come, starting ...')
                        break
            time.sleep(10)

        newrun.status = SearchRun.RUNNING
        newrun.save()
        p = Thread(target=_run_search, args=(request, newrun, rn, c), name='run-search')
        p.start()
        tmp_procs.append(p)

    for p in tmp_procs:
        p.join()

    # check that search has not been deleted
    if not SearchGroup.objects.filter(pk=newgroup.pk).exists():
        logger.warning('SearchGroup %s has been deleted, exiting ...', newgroup.pk)
        return

    p = Thread(target=_start_union, args=(request, newgroup, rn, c), name='start-union')
    p.start()
    p.join()
    django.db.connection.close()

def runidentipy(request):
    c = {}
    failure = ''
    if not request.session.get('chosen_fasta'):
        failure += 'No database selected. '
    if not request.session.get('chosen_spectra'):
        failure += 'No spectrum files selected. '

    if not request.session.get('runname'):
        c['runname'] = time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        c['runname'] = request.session['runname']
    c['chosenfasta'] = request.session['chosen_fasta']
    c['chosenspectra'] = request.session['chosen_spectra']
    c['SearchForms'] = forms.search_forms_from_request(request)
    c['paramtype'] = request.session['paramtype']
#   if os.path.exists('results/%s/%s' % (str(request.user.id), c['runname'])):
#       failure += 'Results with name "%s" already exist, choose another name' % c['runname']
    if not failure:
        newgroup = SearchGroup(groupname=c['runname'], user=request.user)
        newgroup.save()
        newgroup.add_files(c)
        rn = newgroup.name()
        os.makedirs('results/%s/%s' % (str(newgroup.user.id), newgroup.id))
        newgroup.save()
        newgroup.set_notification()
        newgroup.set_FDRs()
        t = Thread(target=_start_all, args=(request, newgroup, rn, c), name='start_all')
        t.start()
        messages.add_message(request, messages.INFO, 'IdentiPy started')
        return redirect('identipy_app:getstatus')
    else:
        messages.add_message(request, messages.INFO, failure)
        return redirect('identipy_app:searchpage')

def search_details(request, pk, c={}):
    runobj = get_object_or_404(SearchGroup, id=pk)
    request.session['searchgroupid'] = runobj.id
    c.update({'searchgroup': runobj})
    sruns = SearchRun.objects.filter(searchgroup_id=runobj.id)
    if sruns.count() == 1:
        request.session['searchrunid'] = sruns[0].id
        return redirect('identipy_app:figure', sruns[0].id)
    return render(request, 'identipy_app/results.html', c)

def results_figure(request, pk):
    c = {}
    runobj = get_object_or_404(SearchRun, id=pk)
    c.update({'searchrun': runobj, 'searchgroup': runobj.searchgroup})
    return render(request, 'identipy_app/results_figure.html', c)


def showparams(request):
    c = {}
    searchgroupid = request.session.get('searchgroupid')
    runobj = get_object_or_404(SearchGroup, id=searchgroupid)
    params_file = runobj.parameters
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(params_file.path())
    logger.debug('Showing params from file %s', params_file.path())

    c['SearchForms'] = {}
    for sftype in ['main'] + (['postsearch'] if c.get('paramtype', 3) == 3 else []):
        c['SearchForms'][sftype] = forms.SearchParametersForm(raw_config=raw_config, user=request.user, label_suffix='', sftype=sftype, prefix=sftype)
    fastas = runobj.fasta.all()
    if len(fastas):
        c['fastaname'] = ' + '.join(f.name() for f in fastas)
    else:
        c['fastaname'] = 'unknown'

    c['searchrun'] = runobj
    return render(request, 'identipy_app/params.html', c)


def show(request):
    c = {}
    ftype = request.GET.get('show_type', request.session.get('show_type'))
    dbname = request.GET.get('dbname', '')
    if (not dbname and ftype != request.session.get('show_type', '')) and not request.GET.get('download_custom_csv', ''):
        request.session['dbname'] = ''
    elif not dbname:
        dbname = request.session.get('dbname', '')
    request.session['show_type'] = ftype
    runid = request.GET.get('runid', request.session.get('searchrunid'))
    request.session['searchrunid'] = runid
    searchgroupid = request.session.get('searchgroupid')
    order_by_label = request.GET.get('order_by', '')
    order_reverse = request.session.get('order_reverse', False)
    order_reverse = not order_reverse if order_by_label == request.session.get('order_by') else order_reverse
    request.session['order_reverse'] = order_reverse
    request.session['order_by'] = order_by_label
    django.db.connection.close()
    runobj = SearchRun.objects.get(id=runid, searchgroup_id=searchgroupid)
    res_dict = runobj.get_detailed(ftype=ftype)
    if order_by_label:
        dbname = request.session.get('dbname', '')
        res_dict.custom_order(order_by_label, order_reverse)
    if dbname:
        request.session['dbname'] = dbname
        res_dict.filter_dbname(dbname)
    labelname = 'Select columns for %ss' % (ftype, )
    sname = 'whitelabels' + ' ' + ftype
    if request.POST.get('choices'):
        res_dict.labelform = forms.MultFilesForm(request.POST, custom_choices=zip(res_dict.labels, res_dict.labels), labelname=labelname, multiform=True)
        if res_dict.labelform.is_valid():
            whitelabels = [x for x in res_dict.labelform.cleaned_data.get('choices')]
            request.session[sname] = whitelabels
            res_dict.custom_labels(whitelabels)
    elif request.session.get(sname, ''):
        whitelabels = request.session.get(sname)
        res_dict.custom_labels(whitelabels)        
    res_dict.labelform = forms.MultFilesForm(custom_choices=zip(res_dict.labels, res_dict.labels), labelname=labelname, multiform=True)
    res_dict.labelform.fields['choices'].initial = res_dict.get_labels()
    c.update({'results_detailed': res_dict})
    runobj = SearchRun.objects.get(id=runid, searchgroup_id=searchgroupid)
    c.update({'searchrun': runobj, 'searchgroup': runobj.searchgroup})

    if request.GET.get('download_custom_csv', ''):
        tmpfile_name = runobj.searchgroup.groupname + '_' + runobj.name() + '_' + ftype + 's_selectedfields.csv'
        tmpfile = tempfile.NamedTemporaryFile(mode='w', prefix='tmp', delete=False)
        tmpfile.write('\t'.join(res_dict.get_labels()) + '\n')
        tmpfile.flush()
        for v in res_dict.get_values(rawformat=True):
            tmpfile.write('\t'.join(v) + '\n')
            tmpfile.flush()
        tmpfile_path = tmpfile.name
        tmpfile.close()

        response = HttpResponse(content_type='application/force-download')
        response['Content-Disposition'] = 'attachment; filename=%s' % smart_str(tmpfile_name)
        response.write(open(tmpfile_path).read())
        os.remove(tmpfile_path)
        return response
    else:
        return render(request, 'identipy_app/results_detailed.html', c)


def getfiles(request, usedclass=False):
    filenames = []
    if request.method == 'POST' and usedclass:
        cc = []
        documents = usedclass.objects.filter(user=request.user)
        for doc in documents:
            cc.append((doc.id, doc.name()))
        form = forms.MultFilesForm(request.POST, custom_choices=cc, labelname=None)
        if form.is_valid():
            for x in form.cleaned_data.get('choices'):
                obj = usedclass.objects.get(user=request.user, id=x)
                filenames.append(obj.path())
                logger.debug('Appending object: %s', obj.path())
        zip_subdir = 'down_files'
    elif request.method == 'GET':
        down_type = request.GET['down_type']
        searchgroupid = request.session.get('searchgroupid')
        searchgroup = SearchGroup.objects.get(id=searchgroupid)
        runid = request.GET.get('runid')
        if runid is not None:
            runs = [SearchRun.objects.get(id=runid)]
        else:
            runs = searchgroup.get_searchruns_all()
        for searchrun in runs:
            if down_type == 'csv':
                for down_fn in searchrun.get_csvfiles_paths():
                    filenames.append(down_fn)
            elif down_type == 'pepxml':
                filtered = bool(request.GET.get('filtered'))
                for down_fn in searchrun.get_pepxmlfiles_paths(filtered=filtered):
                    filenames.append(down_fn)
            elif down_type == 'mgf':
                for down_fn in searchrun.get_spectrafiles_paths():
                    filenames.append(down_fn)
            elif down_type == 'figs':
                for down_fn in searchrun.get_resimage_paths():
                    filenames.append(down_fn)
            elif down_type == 'figs_svg':
                for down_fn in searchrun.get_resimage_paths(ftype='.svg'):
                    filenames.append(down_fn)

        if not filenames:
            logger.debug('Empty download of type %s requested for runs %s. Redirecting...', down_type, [r.id for r in runs])
            messages.add_message(request, messages.INFO, 'No files of this type are available for download.')
            return redirect(request.META.get('HTTP_REFERER', 'identipy_app:getstatus'))
        zip_subdir = searchgroup.name() + '_' + down_type + '_files'

    zip_filename = "%s.zip" % zip_subdir

    s = StringIO.StringIO()
    zf = zipfile.ZipFile(s, "w")

    for fpath in filenames:
        fdir, fname = os.path.split(fpath)
        zip_path = os.path.join(zip_subdir, fname)
        zf.write(fpath, zip_path)
    zf.close()
    logger.info('Downloading ZIP file: %s', zip_filename)

    resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
    resp['Content-Disposition'] = 'attachment; filename=%s' % smart_str(zip_filename)
    return resp
