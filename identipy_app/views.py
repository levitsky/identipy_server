# -*- coding: utf-8 -*-
import django
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.core.files import File
from django.contrib import messages
from django.db.models import Max
from django.utils.encoding import smart_str
from django.template import Template, Context
import django.db
from django.views.decorators.cache import cache_page
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from urllib import urlencode
import os
import zipfile
import shutil
import math
import tempfile
import time
from cStringIO import StringIO
import multiprocessing as mp
from threading import Thread
import urllib
import urlparse
import glob
import gzip
from itertools import izip_longest
import logging
logger = logging.getLogger(__name__)

from pyteomics import parser, mass, pepxml, mgf, mzml
os.chdir(settings.BASE_DIR)
from identipy import main, utils
import scavager.main

from . import forms, models, aux

RUN_LIMIT = getattr(settings, 'NUMBER_OF_PARALLEL_RUNS', 1)


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
        aux.save_params_new(sforms, request.user, False, sessiontype)
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
                _ = forms.search_forms_from_request(request, ignore_post=True)
        request.session['paramtype'] = c['paramtype'] = gettype
    return redirect(*redirect_map[action])


def save_parameters(request):
    sforms = forms.search_forms_from_request(request, ignore_post=True)
    aux.save_params_new(sforms, request.user, request.session.get('paramsname'), request.session.get('paramtype', 3))
    messages.add_message(request, messages.INFO, 'Parameters saved.')
    return redirect('identipy_app:searchpage')


def index(request):
    # TODO: fix the double "if logged in" logic
    if request.user.is_authenticated():
        return redirect('identipy_app:searchpage')
    return redirect('identipy_app:loginform')


def details(request, pK):
    doc = get_object_or_404(models.SpectraFile, id=pK)
    return render(request, 'identipy_app/details.html', {'document': doc})


def delete(request, usedclass):
    usedname = usedclass.__name__
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
    c = {'current': 'loginform'}
    return render(request, 'identipy_app/login.html', c)


def auth_and_login(request, onsuccess='identipy_app:index', onfail='identipy_app:loginform'):
    user = authenticate(username=request.POST['login'], password=request.POST['password'])
    if user is not None:
        request.session.set_expiry(24*60*60)
        login(request, user)
        messages.add_message(request, messages.INFO, 'Login successful.')
        return redirect(onsuccess)
    else:
        messages.add_message(request, messages.INFO, 'Wrong username or password.')
        return redirect(onfail)


def delete_search(request):
    action = request.POST['submit_action']
    for name, val in request.POST.iteritems():
        if val == u'on':
            obj = get_object_or_404(models.SearchGroup, pk=name)
            if action == 'Delete':
                obj.full_delete()
            elif action == 'Repeat':
                _repeat(request, name)
    if action == 'Repeat':
        messages.add_message(request, messages.INFO, 'Starting bulk repeat.')
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
        c['max_res_page'] = int(math.ceil(float(models.SearchGroup.objects.filter(user=request.user.id, groupname__contains=c['search_run_filter']).count()) / 10))
        res_page = min(res_page, c['max_res_page'])
        processes = models.SearchGroup.objects.filter(user=request.user.id, groupname__contains=c['search_run_filter']).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
    else:
        c['max_res_page'] = int(math.ceil(float(models.SearchGroup.objects.filter(user=request.user.id).count()) / 10))
        res_page = min(res_page, c['max_res_page'])
        processes = models.SearchGroup.objects.filter(user=request.user.id).order_by('date_added')[::-1][10*(res_page-1):10*res_page]
    request.session['res_page'] = res_page
    c.setdefault('res_page', res_page)
    c.update({'processes': processes})
    c['timeStep'] = settings.STATUS_UPDATE_INTERVAL
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
        newdoc = models.SpectraFile(docfile=uploadedfile, user=user)
        newdoc.save()
        return newdoc
    elif fext in {'.fasta', '.faa'}:
        newdoc = models.FastaFile(docfile=uploadedfile, user=user)
        newdoc.save()
        return newdoc
    elif fext == '.cfg':
        newdoc = models.ParamsFile(docfile=uploadedfile, user=user, visible=True, title=os.path.split(name)[-1])
        newdoc.save()
        return newdoc
    else:
        logging.error('Unsupported file uploaded: %s', uploadedfile)


def upload(request):
    c = {}
    c['current'] = 'upload'
    c['system_size'] = aux.get_size(os.path.join('results', str(request.user.id)))
    for dirn in ['spectra', 'fasta', 'params']:
        c['system_size'] += aux.get_size(os.path.join('uploads', dirn, str(request.user.id)))
    c['LOCAL_IMPORT'] = getattr(settings, 'LOCAL_IMPORT', False)
    c['URL_IMPORT'] = getattr(settings, 'URL_IMPORT', False)

    # Handle file upload
    if request.method == 'POST':
        commonform = forms.CommonForm(request.POST, request.FILES)
        error_ret = set()
        if 'commonfiles' in request.FILES:
            for uploadedfile in request.FILES.getlist('commonfiles'):
                z, ret = _dispatch_file_handling(uploadedfile, request.user)
                if z is None: # KeyError occurred in dispatcher
                    logger.error('Unrecognized extension in dispatcher: %s', ret)
                    error_ret.add(ret[0])
                if z:
                    d, outs = ret
                    for _, files in outs:
                        fname, path, opener = files
                        with opener(fname) as f:
                            aux._copy_in_chunks(f, path)
                        _save_uploaded_file(path, request.user)
                    shutil.rmtree(d)
                else:
                    fname, path, opener = ret
                    if fname[-3:] == '.gz':
                        with gzip.GzipFile(fileobj=uploadedfile, mode='rb') as f:
                            aux._copy_in_chunks(f, path)
                        _save_uploaded_file(path, request.user)
                    else:
                        _save_uploaded_file(uploadedfile, request.user)
            if error_ret:
                messages.add_message(request, messages.INFO, 'Extention not supported: ' + ', '.join(error_ret))
            else:
                messages.add_message(request, messages.INFO, 'Upload successful.')
            next = request.session.get('next', [('identipy_app:upload',)])
            return redirect(*next.pop())
        else:
            messages.add_message(request, messages.INFO, 'Choose files for upload.')
            return redirect('identipy_app:upload')
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
        logger.debug('Derived fext %s from fname %s', fext, fname)
        return _dispatch_file_handling(fname, user, lambda x: gzip.open(x, 'rb'), fext)
    if fext == 'zip':
        tmpdir = tempfile.mkdtemp()
        with tempfile.NamedTemporaryFile() as tmpf:
            aux._copy_in_chunks(f, tmpf.name)
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
        return None, (ke.args[0], None, None)
    path = models.upload_to_basic(dirn, os.path.split(fname)[1], user.id)
    name, ext = os.path.splitext(path)
    if ext == '.gz':
        path = name
    logger.debug('Copying to %s', path)
    if opener is None: opener = lambda f: open(f, 'rb')
    return False, (fname, path, opener)


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
        outs = []
        for _, out in rets:
            f, path, opener = out
            shutil.copy(f, path)
            outs.append(_save_uploaded_file(path, user))
        shutil.rmtree(tmpdir)
        return outs
    else:
        z, out = _dispatch_file_handling(fname, user)
        fname, path, opener = out
        if z is None:
            return fname
        if not link:
            with opener(fname) as f:
                aux._copy_in_chunks(f, path)
        else:
            logger.debug('Creating symlink: %s -> %s', path, fname)
            os.symlink(fname, path)
        return _save_uploaded_file(path, user)


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
        logger.debug('Local import called with: %s (link=%s)', fname, link)
        if os.path.isfile(fname):
            ret = _local_import(fname, request.user, link)
            if isinstance(ret, (list, models.SpectraFile, models.FastaFile)):
                message = 'Import successful.'
            elif isinstance(ret, basestring):
                message = 'Unsupported file extension: {}'.format(ret)
            else:
                raise ValueError(ret)
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
    logger.debug('URL import worker started with URL: %s', fname)
    parsed = urlparse.urlparse(fname)
    local_name = os.path.split(parsed.path)[1]
    prefix, suffix = os.path.splitext(local_name)
    if suffix == '.gz':
        p2, s2 = os.path.splitext(prefix)
        prefix, suffix = p2, s2 + suffix
    logger.info('Downloading %s ...', fname)
    with tempfile.NamedTemporaryFile(suffix=suffix, mode='rb+') as tmpfile:
        try:
            urllib.urlretrieve(fname, tmpfile.name)
        except IOError as e:
            logger.error('Error while trying to download %s: %s', fname, e)
            return
        logger.info('Saved %s to %s', fname, tmpfile.name)
        doc = _local_import(tmpfile.name, request.user)
    # now we need to restore the local name
    if suffix == '.zip':
        pass
    else:
        final_dir, tmpname = os.path.split(doc.docfile.name)
        lfname = prefix if suffix == 'gz' else local_name
        newname = os.path.join(final_dir, lfname)
        os.rename(doc.docfile.name, newname)
        logger.debug('Renaming: %s -> %s', doc.docfile.name, newname)
        doc.docfile.name = newname
        doc.save()
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
    for key, klass in zip(['spectra', 'fasta'], [models.SpectraFile, models.FastaFile]):
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
    if all(z in request.POST for z in ['subject', 'message']):
        form = forms.ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            from_email = request.user.email
            message = form.cleaned_data['message']
            messages.add_message(request, messages.INFO,
                'Your message was sent to the developers. We will respond as soon as possible.')
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
                    if not models.Modification.objects.filter(user=request.user, label=mod_label, mass=mod_mass, aminoacid=aminoacid).count():
                        modification_object = models.Modification(name=mod_name+aminoacid, label=mod_label, mass=mod_mass, aminoacid=aminoacid, user=request.user)
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
    for pr in models.Protease.objects.filter(user=request.user):
        cc.append((pr.id, '%s (rule: %s)' % (pr.name, pr.rule)))

    if request.POST.get('submit_action', '') == 'delete':
        if request.POST.get('choices'):
            proteases = forms.MultFilesForm(request.POST, custom_choices=cc, labelname='proteases', multiform=True)
            if proteases.is_valid():
                for obj_id in proteases.cleaned_data.get('choices'):
                    obj = models.Protease.objects.get(user=request.user, id=obj_id)
                    obj.delete()
        cc = []
        for pr in models.Protease.objects.filter(user=request.user):
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
            if models.Protease.objects.filter(user=request.user, name=protease_name).count():
                messages.add_message(request, messages.INFO, 'Cleavage rule with name %s already exists' % (protease_name, ))
                return render(request, 'identipy_app/add_protease.html', c)
            try:
                protease_rule = c['proteaseform'].cleaned_data['cleavage_rule']
            except:
                messages.add_message(request, messages.INFO, 'Cleavage rule is incorrect')
                return render(request, 'identipy_app/add_protease.html', c)
            protease_order_val = models.Protease.objects.filter(user=request.user).aggregate(Max('order_val'))['order_val__max'] + 1
            protease_object = models.Protease(name=protease_name, rule=protease_rule, order_val=protease_order_val, user=request.user)
            protease_object.save()
            messages.add_message(request, messages.INFO, 'A new cleavage rule was added')
            sforms = forms.search_forms_from_request(request, ignore_post=True)
            e = sforms['main'].fields['enzyme']
            proteases = models.Protease.objects.filter(user=request.user).order_by('order_val')
            choices = [(p.rule, p.name) for p in proteases]
            e.choices = choices
            aux.save_params_new(sforms, request.user, False, request.session['paramtype'])
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

    usedclass = {'spectra': models.SpectraFile, 'fasta': models.FastaFile, 'params': models.ParamsFile,
            'mods': models.Modification}[what]
    c = {}
    multiform = (usedclass in {models.SpectraFile, models.Modification})
    documents = usedclass.objects.filter(user=request.user)
    choices = []
    for doc in documents:
        if what == 'mods':
            # if not fixed or (not doc.aminoacid.count('[') and not doc.aminoacid.count(']')):
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
                aux.save_mods(uid=request.user, chosenmods=chosenfiles, fixed=fixed, paramtype=request.session['paramtype'])
                key = 'fixed' if fixed else 'variable'
                sforms['main'][key].initial = ','.join(mod.get_label() for mod in chosenfiles)
                aux.save_params_new(sforms, request.user, False, request.session['paramtype'])
            if what == 'params':
                paramfile = chosenfiles[0]
                parname = paramfile.docfile.name
                dst = os.path.join(os.path.dirname(parname), 'latest_params_%s.cfg' % (paramfile.type))
                logger.debug('Copy: %s -> %s', parname, dst)
                shutil.copy(parname, dst)
                request.session['paramtype'] = paramfile.type
                # save_params_new(sforms, request.user, False, request.session['paramtype'])
            else:
                request.session['chosen_' + what] = chosenfilesids
            return redirect('identipy_app:searchpage')
    else:
        kwargs = dict(custom_choices=choices, multiform=multiform)
        if what == 'mods':
            kwargs['labelname'] = 'Select {} modifications:'.format('fixed' if fixed else 'variable')
        form = forms.MultFilesForm(**kwargs)
        if what == 'mods' and not fixed:
            initvals = [mod.id for mod in models.Modification.objects.filter(name__in=['ammoniumlossC', 'ammoniumlossQ', 'waterlossE'])]
            form.fields['choices'].initial = initvals

    c.update({'form': form, 'used_class': what})
    return render(request, 'identipy_app/choose.html', c)


def _enzyme_rule(request, idsettings):
    enz = idsettings.get('search', 'enzyme')
    protease = models.Protease.objects.filter(user=request.user, name=enz).first()
    return protease.rule + '|' + idsettings.get_choices('search', 'enzyme')


def _run_search(request, newrun, generated_db_path):
    django.db.connection.ensure_connection()
    # logger.debug('run-search (%s): connection ensured.', newrun.id)
    sg = newrun.searchgroup
    paramfile = sg.parameters.path()
    fastafile = sg.fasta.all()[0].path()
    idsettings = main.settings(paramfile)
    idsettings.set('search', 'enzyme', _enzyme_rule(request, idsettings))
    idsettings.set('misc', 'iterate', 'peptides')
    if generated_db_path:
        # gpath = aux.generated_db_path(sg)
        logger.debug('Substituting database path to %s for run %s in group %s', generated_db_path, newrun.id, sg.id)
        idsettings.set('input', 'database', generated_db_path)
        idsettings.set('search', 'add decoy', 'no')
    else:
        logger.debug('Not substituting FASTA path (condition is %s)', generated_db_path)
        idsettings.set('input', 'database', fastafile)
    idsettings.set('output', 'path', sg.dirname())
    _totalrun(request, idsettings, newrun, paramfile)
    if _exists(newrun):
        newrun.status = models.SearchRun.VALIDATION
        newrun.save()
        logger.debug('Run %s finished.', newrun.id)
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
    if not models.SearchRun.objects.filter(pk=run.pk).exists():
        logger.info('The SearchRun object %s has been deleted, exiting ...', run.pk)
        return False
    return True


def _save_pepxml(filename, run, filtered=False):
    try:
        with open(filename, 'rb') as fl:
            djangofl = File(fl)
            pepxmlfile = models.PepXMLFile(docfile=djangofl, user=run.searchgroup.user,
                run=run, filtered=filtered)
            pepxmlfile.save()
        if pepxmlfile.docfile.name != filename:
            logger.debug('Removing original pepXML file: %s', filename)
            os.remove(filename)
        logger.info('pepXML file %s saved for run %s.', filename, run.id)
        return pepxmlfile
    except (OSError, IOError) as e:
        logger.error('Could not import file %s for run %s: %s', filename, run.id, e.args)


def _totalrun(request, idsettings, newrun, paramfile):
    django.db.connection.ensure_connection()
    logger.debug('total-run (%s): connection ensured.', newrun.id)
    inputfile = newrun.spectra.path()
    p = mp.Process(target=_runproc, args=(inputfile, idsettings))
    p.start()
    newrun.processpid = p.pid
    newrun.save()
    logger.debug('Process %s started by run %s.', p.pid, newrun.id)
    p.join()
    logger.debug('Process %s joined by run %s.', p.pid, newrun.id)

    filename = _set_pepxml_path(idsettings, inputfile)
    _save_pepxml(filename, newrun)
    if not _exists(newrun):
        logger.warning('Run %s killed after completing the search.', newrun.id)
        return
    django.db.connection.close()


def _runproc(inputfile, idsettings):
    utils.write_pepxml(inputfile, idsettings, main.process_file(inputfile, idsettings))


def _save_csv(suffix, ftype, run, bname):
    logger.debug('Importing: %s', bname + suffix)
    filename = bname + suffix
    if os.path.exists(filename):
        with open(filename) as fl:
            djangofl = File(fl)
            csvf = models.ResCSV(docfile=djangofl, user=run.searchgroup.user,
                ftype=ftype, run=run, filtered=(not suffix.endswith('_full.tsv')))
            csvf.save()
        if csvf.docfile.name != filename:
            logger.debug('Removing original CSV file: %s', filename)
            os.remove(filename)
        return csvf
    else:
        logger.debug('File not found.')


def _get_img_type(fname):
    if fname[:4] == 'PSMs':
        return models.ResImageFile.PSM
    if fname[:8] == 'peptides':
        return models.ResImageFile.PEPTIDE
    if 'NSAF' in fname or 'sequence coverage' in fname:
        return models.ResImageFile.PROTEIN
    return models.ResImageFile.OTHER


def _save_img(filename, run):
    ftype = os.path.splitext(filename)[-1]
    base = os.path.basename(filename)
    imgtype = _get_img_type(base)
    with open(filename) as fl:
        djangofl = File(fl)
        img = models.ResImageFile(docfile=djangofl, user=run.searchgroup.user,
            ftype=ftype, run=run, imgtype=imgtype)
        img.save()
    if img.docfile.name != filename:
        logger.debug('Removing original CSV file: %s', filename)
        os.remove(filename)
    logger.debug('Imported: %s', img.docfile.path)
    return img


def _post_process(request, searchgroup, generated_db_path):
    logger.info('Starting Scavager for group %s ...', searchgroup.id)
    if searchgroup.searchrun_set.count() > 1:
        union = searchgroup.searchrun_set.get(union=True)
        union.status = models.SearchRun.RUNNING
        union.save()
    pfiles = []
    for run in searchgroup.searchrun_set.filter(union=False).order_by('id'):
        files = run.get_pepxmlfiles_paths()
        pfiles.extend(files)
    idsettings = main.settings(searchgroup.parameters.path())
    if generated_db_path:
        dbpath = aux.generated_db_path(searchgroup)
    else:
        dbpath = searchgroup.fasta.all()[0].docfile.path
    scavager_args = {
            'file': pfiles,
            'database': dbpath,
            'prefix': idsettings.get('input', 'decoy prefix').strip(),
            'infix': idsettings.get('input', 'decoy infix').strip(),
            'union': True,
            'separate_figures': True,
            'create_pepxml': True,
            'output': searchgroup.dirname(),
            'fdr': idsettings.getfloat('options', 'FDR'),
            'enzyme': models.Protease.objects.filter(
                user=request.user, name=idsettings.get('search', 'enzyme')
                ).first().rule,
            'allowed_peptides': None,
            'group_prefix': None,
            'group_infix': None,
            'quick_union': None,
            'no_correction': True,
            'force_correction': False,
            'name_suffix': '',
            'pif_threshold': None,
        }
    logger.debug('Scavager args: %s', scavager_args)
    retv = scavager.main.process_files(scavager_args)
    if isinstance(retv, int) and retv < 0:
        for run in searchgroup.searchrun_set.all():
            run.status = models.SearchRun.ERROR
            run.save()
        logger.error('Scavager for group %s finished with an error (%s).', searchgroup.id, retv)
        return

    logger.info('Finished Scavager for group %s.', searchgroup.id)
    if isinstance(retv, int):
        retv = (retv, )

    for v, run in izip_longest(retv, searchgroup.searchrun_set.order_by('id')):
        if v is None or v < 0:
            run.status = models.SearchRun.ERROR
            run.save()
            logger.info('Marking run %s as ERROR based on scavager return value %s, skipping file import.', run.id, v)
            continue
        if run.union:
            bname = os.path.join(searchgroup.dirname(), 'union')
        else:
            pepxmllist = run.get_pepxmlfiles_paths()
            bname = pepxmllist[0].split('.pep.xml')[0]
        logger.debug('Collecting results for %s ...', bname)
        if not _exists(run):
            logger.warning('Run %s killed after completing Scavager.', run.id)
        dname = os.path.join(searchgroup.dirname(), os.path.basename(bname) + '_figures')
        try:
            for tmpfile in os.listdir(dname):
                _save_img(os.path.join(dname, tmpfile), run)
        except OSError as e:
            logger.error('Could not import figures for search group %s from %s: %s',
                searchgroup.id, dname, e.args)

        for suffix, ftype in [('_PSMs.tsv', 'psm'), ('_PSMs_full.tsv', 'psm'), ('_peptides.tsv', 'peptide'),
                ('_proteins.tsv', 'protein'), ('_protein_groups.tsv', 'prot_group')]:
            _save_csv(suffix, ftype, run, bname)
        _save_pepxml(bname + '.scavager.pep.xml', run=run, filtered=True)

        if run.union:
            runs = searchgroup.get_searchruns_all()
            filenames_tmp = [f.docfile.name
                for run in runs for f in run.rescsv_set.filter(ftype='protein')]
            outpath_tmp = bname + '_LFQ.tsv'
            if filenames_tmp:
                aux.process_LFQ(filenames_tmp, outpath_tmp)
                with open(outpath_tmp) as fl:
                    djangofl = File(fl)
                    csvf = models.ResCSV(docfile=djangofl, user=request.user, ftype='lfq', run=run)
                    csvf.save()

        run.calc_results()
        run.status = models.SearchRun.FINISHED
        run.save()

    if searchgroup.notification:
        aux.email_to_user(searchgroup)

    logger.info('Group %s finished.', searchgroup.id)


def _start_all(request, newgroup):
    django.db.connection.ensure_connection()
    generated = aux.generate_database(newgroup)
    tmp_procs = []
    for newrun in newgroup.get_searchruns():
        have_waited = False
        while True:
            running = models.SearchRun.objects.filter(status=models.SearchRun.RUNNING)
            nr = running.count()
            logger.debug('%s runs currently running.', nr)
            if nr == 0:
                logger.debug('Server idle, starting %s right away ...', newrun.id)
                break
            elif nr >= RUN_LIMIT:
                if not have_waited:
                    logger.debug('Too many active runs, %s waiting ...', newrun.id)
                    have_waited = True
            else:
                last_user = running.latest('last_update').searchgroup.user
                logger.debug('Last user: %s', last_user.username)
                try:
                    next_user = models.SearchRun.objects.filter(status=models.SearchRun.WAITING).exclude(
                            searchgroup__user=last_user).earliest('last_update').searchgroup.user
                except models.SearchRun.DoesNotExist:
                    logger.debug('No competing users, starting %s ...', newrun.id)
                    break
                else:
                    logger.debug('Next user: %s', next_user)
                    if next_user == newrun.searchgroup.user:
                        logger.debug('My turn has come, starting %s ...', newrun.id)
                        break
            time.sleep(30)

        newrun.status = models.SearchRun.RUNNING
        newrun.save()
        p = Thread(target=_run_search, args=(request, newrun, generated), name='run-search')
        p.start()
        tmp_procs.append(p)

    for p in tmp_procs:
        p.join()

    # check that search has not been deleted
    if not models.SearchGroup.objects.filter(pk=newgroup.pk).exists():
        logger.warning('SearchGroup %s has been deleted, exiting ...', newgroup.pk)
        return

    _post_process(request, newgroup, generated)
    django.db.connection.close()


def _sg_from_context(c, user):
    newgroup = models.SearchGroup(groupname=c['runname'], user=user)
    newgroup.save()
    newgroup.add_files(c)
    os.makedirs(newgroup.dirname())
    newgroup.save()
    newgroup.set_notification()
    newgroup.set_FDR()
    return newgroup


def _sg_context_from_request(request):
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
    if not failure:
        c['chosenfasta'] = request.session['chosen_fasta']
        c['chosenspectra'] = request.session['chosen_spectra']
        c['SearchForms'] = forms.search_forms_from_request(request)
        c['paramtype'] = request.session['paramtype']
    return failure, c


def _sg_context_from_sg(sg):
    c = {}
    c['runname'] = sg.groupname
    c['chosenfasta'] = sg.fasta.all()
    c['chosenspectra'] = [r.spectra.id for r in sg.searchrun_set.filter(union=False)]
    paramobj = sg.parameters
    c['SearchForms'] = forms.search_form_for_params(paramobj)
    c['paramtype'] = 3
    return c


def _repeat(request, sgid):
    sg = get_object_or_404(models.SearchGroup, pk=sgid)
    c = _sg_context_from_sg(sg)
    newgroup = _sg_from_context(c, request.user)
    t = Thread(target=_start_all, args=(request, newgroup), name='start_all')
    t.start()


def repeat_search(request, sgid):
    _repeat(request, sgid)
    messages.add_message(request, messages.INFO, 'IdentiPy started')
    return redirect('identipy_app:getstatus')


def runidentipy(request):
    failure, c = _sg_context_from_request(request)
    if not failure:
        newgroup = _sg_from_context(c, request.user)
        t = Thread(target=_start_all, args=(request, newgroup), name='start_all')
        t.start()
        messages.add_message(request, messages.INFO, 'IdentiPy started')
        return redirect('identipy_app:getstatus')
    else:
        messages.add_message(request, messages.INFO, failure)
        return redirect('identipy_app:searchpage')


def search_details(request, pk):
    group = get_object_or_404(models.SearchGroup, id=pk)
    c = {'searchgroup': group}
    sruns = group.searchrun_set.all()
    if len(sruns) == 1:
#       request.session['searchrunid'] = sruns[0].id
        return redirect('identipy_app:figure', sruns[0].id)
    rename_form = forms.RenameForm()
    c['rename_form'] = rename_form
    return render(request, 'identipy_app/results.html', c)


def results_figure(request, pk):
    runobj = get_object_or_404(models.SearchRun, id=pk)
    c = {'searchrun': runobj, 'searchgroup': runobj.searchgroup}
    if len(runobj.searchgroup.searchrun_set.all()) == 1:
        rename_form = forms.RenameForm()
        c['rename_form'] = rename_form
    figures = []
    for val, name in models.ResImageFile.IMAGE_TYPES:
        figures.append((name, runobj.resimagefile_set.filter(imgtype=val)))
    c['figures'] = figures
    c['dfigs'] = len(runobj.resimagefile_set.filter(imgtype=models.ResImageFile.OTHER))
    return render(request, 'identipy_app/results_figure.html', c)


def showparams(request, searchgroupid):
    c = {}
    runobj = get_object_or_404(models.SearchGroup, id=searchgroupid)
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
    ftype = request.GET.get('show_type')
    c['ftype'] = ftype
    runid = request.GET.get('runid')
    orderby = request.GET.get('order_by')
    ascending = 1 - int(request.GET.get('reverse', 0))
    protein = request.GET.get('dbname')
    peptide = request.GET.get('peptide')
    c['order_by'] = orderby
    c['reverse'] = not ascending
    runobj = get_object_or_404(models.SearchRun, id=runid)
    res_dict = aux.ResultsDetailed(runobj, ftype, orderby, ascending, protein, peptide)

    labelname = 'Select columns for {}s'.format(ftype)
    sname = 'whitelabels ' + ftype
    if request.POST.get('choices'):
        res_dict.labelform = forms.MultFilesForm(request.POST,
            custom_choices=zip(res_dict.visible_columns, res_dict.visible_columns), labelname=labelname, multiform=True)
        if res_dict.labelform.is_valid():
            whitelabels = [x for x in res_dict.labelform.cleaned_data.get('choices')]
            request.session[sname] = whitelabels
            res_dict.custom_labels(whitelabels)
        logger.debug('GET: %s', request.GET)
        return redirect(reverse('identipy_app:show') + '?' + urlencode(request.GET))

    elif request.session.get(sname):
        whitelabels = request.session[sname]
        res_dict.custom_labels(whitelabels)
    if request.method == 'GET':
        res_dict.labelform = forms.MultFilesForm(
            custom_choices=zip(res_dict.visible_columns, res_dict.visible_columns), labelname=labelname, multiform=True)
    res_dict.labelform.fields['choices'].initial = res_dict.get_labels()
    c.update({'results_detailed': res_dict, 'searchrun': runobj})

    if request.GET.get('download_custom_csv'):
        tmpfile_name = runobj.searchgroup.groupname + '_' + runobj.name() + '_' + ftype + 's_selectedfields.tsv'
        tmpfile = tempfile.NamedTemporaryFile(mode='w', prefix='tmp', delete=False)

        tmpfile_path = tmpfile.name
        res_dict.output_table(True).to_csv(tmpfile_path, index=False, sep='\t')
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
        by_group = False
        down_type = request.GET['down_type']
        runid = request.GET.get('run')
        if runid is not None:
            run = get_object_or_404(models.SearchRun, id=runid)
            runs = [run]
            searchgroup = run.searchgroup
        else:
            by_group = True
            searchgroup = get_object_or_404(models.SearchGroup, pk=request.GET.get('group'))
            runs = searchgroup.get_searchruns_all()
        for searchrun in runs:
            if down_type == 'csv':
                filenames = [doc.docfile.path for doc in searchrun.rescsv_set.all()]
            elif down_type == 'pepxml':
                filtered = request.GET.get('filtered') == 'true'
                if by_group and searchrun.union and not filtered:
                    continue
                for down_fn in searchrun.get_pepxmlfiles_paths(filtered=filtered):
                    filenames.append(down_fn)
            elif down_type == 'mgf':
                for down_fn in searchrun.get_spectrafiles_paths():
                    filenames.append(down_fn)
            elif down_type == 'figs':
                filenames = [doc.docfile.path for doc in searchrun.resimagefile_set.all()]

        if not filenames:
            logger.debug('Empty download of type %s requested for runs %s. Redirecting...', down_type, [r.id for r in runs])
            messages.add_message(request, messages.INFO, 'No files of this type are available for download.')
            return redirect(request.META.get('HTTP_REFERER', 'identipy_app:getstatus'))
        zip_subdir = searchgroup.name() + '_' + down_type + '_files_'
        if len(runs) == 1:
            zip_subdir += runs[0].name()
        else:
            zip_subdir += 'all'

    zip_filename = zip_subdir + '.zip'
    logger.debug('Creating archive %s ...', zip_filename)
    s = StringIO()

    with zipfile.ZipFile(s, 'w', settings.ZIP_COMPRESSION, settings.ALLOW_ZIP64) as zf:
        for fpath in filenames:
            fdir, fname = os.path.split(fpath)
            zip_path = os.path.join(zip_subdir, fname)
            zf.write(fpath, zip_path)

    logger.info('Downloading ZIP file: %s', zip_filename)
    resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
    s.close()
    resp['Content-Disposition'] = 'attachment; filename=%s' % smart_str(zip_filename)
    logger.debug('Returning response with %s.', zip_filename)
    return resp


def group_status(request, sgid):
    sg = get_object_or_404(models.SearchGroup, id=sgid)
    return JsonResponse({
        'status': sg.get_status(),
        'updated': Template('{{ date }}').render(Context({'date': sg.get_last_update()})),
        'done': sum(r.status in {models.SearchRun.FINISHED, models.SearchRun.VALIDATION}
            for r in sg.searchrun_set.all()),
        'total': len(sg.searchrun_set.all())
        })


@cache_page(30*60)
def spectrum(request):
    def save_offsets(reader):
        try:
            if not reader._check_has_byte_offset_file():
                reader.write_byte_offsets()
        except AttributeError as e:
            logger.warning('Could not save %s index. Is Pyteomics 4.1+ installed?', reader.__class__.__name__)
            logger.debug('%s', e)

    title = urllib.unquote_plus(request.GET['spectrum'])
    run = get_object_or_404(models.SearchRun, pk=request.GET['runid'])
    assert not run.union
    pepname = run.get_pepxmlfiles_paths()[0]
    with pepxml.PepXML(pepname) as reader:
        result = reader[title]
        save_offsets(reader)
    specfile = run.spectra.docfile.path
    idsettings = main.settings(run.searchgroup.parameters.path())
    utils.set_mod_dict(idsettings)
    klass = {'.mgf': mgf.IndexedMGF, '.mzml': mzml.MzML}[os.path.splitext(specfile)[1].lower()]
    with klass(specfile, read_charges=False) as reader:
        spectrum = reader[title]
        save_offsets(reader)
    aa_mass = utils.get_aa_mass(idsettings)
    # fix masses of terminal mods
    for key, value in aa_mass.items():
        if key[0] == '-':
            aa_mass[key] = value + aa_mass['protein cterm cleavage']
        elif key[-1] == '-':
            aa_mass[key] = value + aa_mass['protein nterm cleavage']
    ftol = idsettings.getfloat('search', 'product accuracy')
    modseq = parser.parse(result['search_hit'][0]['peptide'])
    seqshift = -1
    for mod in result['search_hit'][0]['modifications']:
        pos = mod['position']
        if pos == 0:
            label = min([i for i in aa_mass.items() if i[0][-1] == '-'],
                    key=lambda i: abs(i[1]+aa_mass['protein nterm cleavage']-mod['mass']))[0]
            modseq.insert(0, label)
            seqshift = 0
        elif pos == len(result['search_hit'][0]['peptide']) + 1:
            label = min([i for i in aa_mass.items() if i[0][0] == '-'],
                    key=lambda i: abs(i[1]+aa_mass['protein cterm cleavage']-mod['mass']))[0]
            modseq.append(label)
        else:
            aa = modseq[mod['position']+seqshift]
            if abs(aa_mass[aa] - mod['mass']) > 0.001:
                label = min([i for i in aa_mass.items() if i[0][-1] == aa],
                    key=lambda i: abs(i[1]-mod['mass']))[0]
                modseq[mod['position']+seqshift] = label
    modseq = parser.tostring(modseq, True)
    logger.debug('Visualizing spectrum %s from file %s, peptide %s (%s).',
            title, pepname, result['search_hit'][0]['peptide'], modseq)
    figure = aux.spectrum_figure(spectrum, modseq, title=modseq, aa_mass=aa_mass, ftol=ftol)
    context = {'result': result, 'figure': figure.decode('utf-8')}
    return render(request, 'identipy_app/spectrum.html', context)


def rename(request, pk):
    if request.method != 'POST':
        return redirect('identipy_app:getstatus')
    form = forms.RenameForm(request.POST)
    if form.is_valid():
        group = get_object_or_404(models.SearchGroup, pk=pk)
        group.groupname = form.cleaned_data['newname']
        group.save()
        messages.add_message(request, messages.INFO, 'Search renamed.')
        return redirect('identipy_app:details', pk)
    messages.add_message(request, messages.ERROR, 'Invalid input.')
    return redirect('identipy_app:details', pk)
