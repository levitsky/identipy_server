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

from pyteomics import parser, mass
os.chdir(settings.BASE_DIR)
sys.path.insert(0, '../identipy/')
sys.path.insert(0, '../mp-score/')
from identipy import main, utils
import MPscore

from .aux import save_mods, save_params_new, ResultsDetailed, get_size, Tasker
from .models import SpectraFile, RawFile, FastaFile, ParamsFile, PepXMLFile, ResImageFile, ResCSV
from .models import SearchGroup, SearchRun, Protease, Modification 
from .models import upload_to_basic
from .forms import MultFilesForm, CommonForm, ContactForm, AddProteaseForm, AddModificationForm, SearchParametersForm
from .forms import search_forms_from_request#, search_params_form


search_limit = getattr(settings, 'NUMBER_OF_PARALLEL_RUNS', 1)

tasker = Tasker()

try:
    searchgroups = SearchGroup.objects.all()
    for searchgroup in searchgroups:
        if not searchgroup.status.startswith('Task finished'):
            searchgroup.change_status('Task is dead')
    #        searchgroup.delete()
    #        shutil.rmtree('results/%s/%s/' % (str(searchgroup.user.id), searchgroup.name().encode('ASCII')))
except:
    print 'Smth wrong with SearchGroup model'

def add_forms(request, c):
    c['paramtype'] = c.get('paramtype')
    if not c['paramtype']:
        c['paramtype'] = request.session.setdefault('paramtype', 3)
    request.session['paramtype'] = c['paramtype']
#   if 'bigform' in request.session:
#       print 'Returning forms from session'
#       c['SearchForms'] = pickle.loads(request.session['bigform'])
#       print c['SearchForms']['main'].fields
#       print '(just kidding, reading file anyway)'
#   else:
    c['SearchForms'] = search_forms_from_request(request)
#       c['SearchForms'] = search_params_form(request)
#   print c['SearchForms']

def form_dispatch(request):
    c = {}
    if request.GET or not request.user.is_authenticated():
        return redirect('identipy_app:index')
    action = request.POST['submit_action']
    if action != 'Search previous runs by name':
#   forms = search_params_form(request)
        forms = search_forms_from_request(request)
        sessiontype = request.session.get('paramtype')
        save_params_new(forms, request.user, False, sessiontype)
#   print forms
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

#   print request.POST.items()
#   print request.POST['submit_action'], '!!!'
    request.session['redirect'] = redirect_map[action]
    request.session['runname'] = request.POST.get('runname')
    request.session['paramsname'] = request.POST.get('paramsname')
#   request.session['next'] = ['searchpage']
    if action in {'Minimal', 'Medium', 'Advanced'}:
        gettype = {'Minimal': 1, 'Medium': 2, 'Advanced': 3}[action]
        if sessiontype != gettype:
#           forms = request.session.pop('bigform', None)
            if forms is not None:
                request.session['paramtype'] = gettype
                newforms = search_forms_from_request(request, ignore_post=True)
#               request.session['bigform'] = pickle.dumps(newforms)
        request.session['paramtype'] = c['paramtype'] = gettype
#   else:
#       request.session['bigform'] = pickle.dumps(forms)

    return redirect(*redirect_map[action])

def save_parameters(request):
#   forms = pickle.loads(request.session['bigform'])
    forms = search_forms_from_request(request, ignore_post=True)
    save_params_new(forms, request.user, request.session.get('paramsname'), request.session.get('paramtype', 3))
    messages.add_message(request, messages.INFO, 'Parameters saved')
    return redirect('identipy_app:searchpage')

def index(request):
    # TODO: fix the double "if logged in" logic
    if request.user.is_authenticated():
        return redirect('identipy_app:searchpage')
#       return render(request, 'identipy_app/index.html', {})
    else:
        return redirect('identipy_app:loginform')

def details(request, pK):
    doc = get_object_or_404(SpectraFile, id=pK)
    return render(request, 'identipy_app/details.html', {'document': doc})

def delete(request, usedclass):
    usedname=usedclass.__name__
#   django.db.connection.close()
    documents = usedclass.objects.filter(user=request.user)
    cc = []
    for doc in documents:
        if not usedname == 'ParamsFile' or not doc.name().startswith('latest_params'):
            try:
                cc.append((doc.id, doc.name()))
            except:
                cc.append((doc.id, doc.name))
    form = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
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
#   django.db.connection.close()
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

#def get_user_latest_params_path(paramtype, userid):
#    return os.path.join('uploads', 'params', str(userid.id), 'latest_params_%d.cfg' % (paramtype, ))

def _save_uploaded_file(uploadedfile, user):
    if isinstance(uploadedfile, basestring):
        fname = uploadedfile
    else:
        fname = uploadedfile.name
    name, fext = os.path.splitext(fname.lower())
    if fext == '.gz':
        name, fext = os.path.splitext(name)
    print 'Determined extension:', fext    
    if fext in {'.mgf', '.mzml'}:
        newdoc = SpectraFile(docfile=uploadedfile, user=user)
        newdoc.save()
    elif fext in {'.fasta', '.faa'}:
        newdoc = FastaFile(docfile=uploadedfile, user=user)
        newdoc.save()
    else:
        print 'Unsupported file uploaded:', uploadedfile

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
        commonform = CommonForm(request.POST, request.FILES)
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
        commonform = CommonForm()

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
#       shutil.rmtree(tmpdir)
        return True, (tmpdir, rets)
    try:
        dirn = {'mgf': 'spectra', 'mzml': 'spectra', 'fasta': 'fasta', 'faa': 'fasta', 'cfg': 'params'}[fext]
    except KeyError as ke:
        return ke.args[0]
    path = upload_to_basic(dirn, os.path.split(fname)[1], user.id)
    name, ext = os.path.splitext(path)
    if ext == '.gz':
        path = name
    print 'Copying to', path
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
        print 'Error importing', f.name, ':', e.args
    else:
        return path


def _local_import(fname, user):
    print 'IMPORTING FILE', fname
    fext = os.path.splitext(fname)[-1][1:].lower()
    if fext == 'zip':
        tmpdir = tempfile.mkdtemp()
        print 'Extracting to', tmpdir
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
        with opener(fname) as f:
            _copy_in_chunks(f, path)
        _save_uploaded_file(path, user)

def local_import(request):
    if request.method == 'POST':
        fname = request.POST.get('filePath').encode('utf-8')
        if os.path.isfile(fname):
            ret = _local_import(fname, request.user)
            if ret is None:
                message = 'Import successful.'
            else:
                message = 'Unsupported file extension: {}'.format(ret)
        else:
            ret = []
            if os.path.isdir(fname):
                for root, dirs, files in os.walk(fname):
                    for f in files:
                        ret.append(_local_import(os.path.join(root, f), request.user))
            else:
                for f in glob.glob(fname):
                    ret.append(_local_import(f, request.user))
            n = sum(r is None for r in ret)
            message = '{} file(s) imported.'.format(n)

        messages.add_message(request, messages.INFO, message)
        next = request.session.get('next', [])
        if next:
            return redirect(*next.pop())

    return redirect('identipy_app:upload')

def url_import(request):
    if request.method == 'POST':
        fname = request.POST.get('fileUrl').encode('utf-8')
        parsed = urlparse.urlparse(fname)
        local_name = os.path.split(parsed.path)[1]
        tmpfile = os.path.join(tempfile.gettempdir(), local_name)
        print 'Downloading', fname, '...'
        urllib.urlretrieve(fname, tmpfile)
        print 'Saved to', tmpfile
        _local_import(tmpfile, request.user)
        os.remove(tmpfile)
        messages.add_message(request, messages.INFO, 'Download successful.')
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
        form = ContactForm(request.POST)
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
                print 'Could not send email:'
                print e
            return redirect('identipy_app:contacts')
    else:
        form = ContactForm(initial={'from_email': request.user.username})
    return render(request, "identipy_app/email.html", {'form': form})


def email_to_user(username, searchname):
    try:
        send_mail('IdentiPy Server notification', 'Search %s was finished' % (searchname, ), 'identipymail@gmail.com', [username, ])
    except Exception as e:
        print 'Could not send email:'
        print e


def add_modification(request):
#   django.db.connection.close()
    c = {}
    if request.method == 'POST':
        c['modificationform'] = AddModificationForm(request.POST)
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
                    print request.session['next']
                    return redirect(*request.session['next'].pop())
                else:
                    return redirect('identipy_app:searchpage')
                # return select_modifications(request, c = c, fixed=c['fixed'])
                # if c['fixed'] == True:
                #     return
                # return searchpage(request, c)
        else:
            messages.add_message(request, messages.INFO, 'All fields must be filled')
            return render(request, 'identipy_app/add_modification.html', c)
    else:
        c['modificationform'] = AddModificationForm()
        return render(request, 'identipy_app/add_modification.html', c)

def add_protease(request):
#   django.db.connection.close()
    c = {}
    cc = []
    for pr in Protease.objects.filter(user=request.user):
        cc.append((pr.id, '%s (rule: %s)' % (pr.name, pr.rule)))

    if request.POST.get('submit_action', '') == 'delete':
        # request.POST = request.POST.copy()
        if request.POST.get('choices'):
            proteases = MultFilesForm(request.POST, custom_choices=cc, labelname='proteases', multiform=True)
            if proteases.is_valid():
                for obj_id in proteases.cleaned_data.get('choices'):
                    obj = Protease.objects.get(user=request.user, id=obj_id)
                    obj.delete()
        # print type(proteases)
        # for p in proteases:
        #     print p
        cc = []
        for pr in Protease.objects.filter(user=request.user):
            cc.append((pr.id, '%s (rule: %s)' % (pr.name, pr.rule)))
        proteases = MultFilesForm(custom_choices=cc, labelname='proteases', multiform=True)
                # request.POST['choices'] = False
                # request.POST.pop('submit_action')
        c['proteaseform'] = AddProteaseForm()
        c['proteases'] = proteases
        return render(request, 'identipy_app/add_protease.html', c)

    proteases = MultFilesForm(custom_choices=cc, labelname='proteases', multiform=True)
    if request.method == 'POST':
        c['proteaseform'] = AddProteaseForm(request.POST)
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
#           if 'bigform' in request.session:
#               sforms = pickle.loads(request.session['bigform'])
            sforms = search_forms_from_request(request, ignore_post=True)
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
        c['proteaseform'] = AddProteaseForm()
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
#   django.db.connection.close()
    c = {}
#   usedname = None
    multiform = (usedclass in {SpectraFile, Modification})
#   c.update({'usedclass': usedclass, 'usedname': usedname})
    documents = usedclass.objects.filter(user=request.user)
    choices = []
    for doc in documents:
        if what == 'mods':
            if not fixed or (not doc.aminoacid.count('[') and not doc.aminoacid.count(']')):
                choices.append((doc.id, '%s (label: %s, mass: %f, aminoacid: %s)' % (doc.name, doc.label, doc.mass, doc.aminoacid)))
        elif what in {'spectra', 'fasta'} or (what == 'params' and (not doc.name().startswith('latest_params') and doc.visible)):
            choices.append((doc.id, doc.name()))
    if request.method == 'POST':
#       request.session.setdefault('next', []).append(('identipy_app:choose', what))
        action = request.POST['submit_action']
        if action == 'upload new files':
            return redirect('identipy_app:upload')
        elif action == 'add custom modification':
            request.session.setdefault('next', []).append(('identipy_app:choose', what_orig))
            return redirect('identipy_app:new_mod')
        elif action == 'download':
            #return redirect('identipy_app:download')
            return getfiles(request, usedclass=usedclass)
        elif action == 'delete':
            #return redirect('identipy_app:download')
            return delete(request, usedclass=usedclass)

        form = MultFilesForm(request.POST, custom_choices=choices)
        if form.is_valid():
            chosenfilesids = [int(x) for x in form.cleaned_data['choices']]
            chosenfiles = usedclass.objects.filter(id__in=chosenfilesids)
            sforms = search_forms_from_request(request, ignore_post=True)
            print sforms
            if what == 'mods':
                save_mods(uid=request.user, chosenmods=chosenfiles, fixed=fixed, paramtype=request.session['paramtype'])
#               sforms = pickle.loads(request.session['bigform'])
                key = 'fixed' if fixed else 'variable' 
                sforms['main'][key].initial = ','.join(mod.get_label() for mod in chosenfiles)
                save_params_new(sforms, request.user, False, request.session['paramtype'])
            if what == 'params':
                paramfile = chosenfiles[0]
                parname = paramfile.docfile.name.encode('utf-8')
                dst = os.path.join(os.path.dirname(parname), 'latest_params_%s.cfg' % (paramfile.type, ))
                shutil.copy(parname, dst)
                request.session['paramtype'] = paramfile.type
#               request.session['bigform'] = pickle.dumps(search_forms_from_request(request, ignore_post=True))
                save_params_new(sforms, request.user, False, request.session['paramtype'])
            else:
                request.session['chosen_' + what] = chosenfilesids
            return redirect('identipy_app:searchpage')
    else:
#       if 'bigform' not in request.session:
#           return redirect('identipy_app:searchpage')
        kwargs = dict(custom_choices=choices, multiform=multiform)
        if what == 'mods':
            kwargs['labelname'] = 'Select {} modifications:'.format('fixed' if fixed else 'variable')
        form = MultFilesForm(**kwargs)
        if what == 'mods' and not fixed:
            initvals = [mod.id for mod in Modification.objects.filter(name__in=['ammoniumlossC', 'ammoniumlossQ', 'waterlossE'])]
            form.fields['choices'].initial = initvals

    c.update({'form': form, 'used_class': what})
    return render(request, 'identipy_app/choose.html', c)

def _run_search(request, newrun, rn, c):
#   django.db.connection.close()
    paramfile = newrun.parameters.all()[0].path()
    fastafile = newrun.fasta.all()[0].path()
    idsettings = main.settings(paramfile)
    enz = idsettings.get('search', 'enzyme')
    protease = Protease.objects.filter(user=request.user, name=enz).first()
    idsettings.set('search', 'enzyme', protease.rule + '|' + idsettings.get_choices('search', 'enzyme'))
    idsettings.set('misc', 'iterate', 'peptides')
    idsettings.set('input', 'database', fastafile.encode('utf-8'))
    idsettings.set('output', 'path', 'results/%s/%s' % (str(newrun.user.id), rn.encode('utf-8')))
    newrun.set_notification(idsettings)
    _totalrun(request, idsettings, newrun, paramfile)
    django.db.connection.close()
    return 1

def _set_pepxml_path(idsettings, inputfile):
    if idsettings.has_option('output', 'path'):
        outpath = idsettings.get('output', 'path')
    else:
        outpath = os.path.dirname(inputfile)
    outpath = outpath.decode('utf-8')
    return os.path.join(outpath, os.path.splitext(
        os.path.basename(inputfile))[0] + os.path.extsep + 'pep' + os.path.extsep + 'xml')

def _totalrun(request, idsettings, newrun, paramfile):
    django.db.connection.close()
    procs = []
    spectralist = newrun.get_spectrafiles_paths()
    fastalist = newrun.get_fastafile_path()
    if not newrun.union:
        for obj in newrun.spectra.all():
            inputfile = obj.path()
#           p = Process(target=_runproc, args=(request, inputfile, idsettings, newrun, request.user))
            p = Thread(target=_runproc, args=(request, inputfile, idsettings, newrun), name='runproc')
            p.start()
            procs.append(p)
        for p in procs:
            p.join()
        pepxmllist = newrun.get_pepxmlfiles_paths()
        paramlist = [paramfile]
        bname = pepxmllist[0].split('.pep.xml')[0].decode('utf-8')
    else:
        pepxmllist = newrun.get_pepxmlfiles_paths()
        paramlist = [paramfile]
        bname = os.path.dirname(pepxmllist[0].decode('utf-8')) + '/union'
    newrun.set_FDRs()
    MPscore.main(['_'] + pepxmllist + spectralist + fastalist + paramlist, union_custom=newrun.union)
    if not os.path.isfile(bname + '_PSMs.csv'):
        bname = os.path.dirname(bname) + '/union'

    dname = os.path.dirname(pepxmllist[0])
    for tmpfile in os.listdir(dname):
        ftype = os.path.splitext(tmpfile)[-1]
        if ftype in {'.png', '.svg'} and newrun.name() + '_' in os.path.basename(tmpfile.decode('utf-8')):
            fl = open(os.path.join(dname, tmpfile).decode('utf-8'))
            djangofl = File(fl)
            img = ResImageFile(docfile = djangofl, user = request.user, ftype=ftype)
            img.save()
            newrun.add_resimage(img)
            fl.close()
    if os.path.exists(bname + '_PSMs.csv'):
        fl = open(bname + '_PSMs.csv'.decode('utf-8'))
        djangofl = File(fl)
        csvf = ResCSV(docfile = djangofl, user = request.user, ftype='psm')
        csvf.save()
        newrun.add_rescsv(csvf)
    if os.path.exists(bname + '_PSMs.pep.xml'):
        fl = open(bname + '_PSMs.pep.xml', 'rb')
        djangofl = File(fl)
        pepxmlfile = PepXMLFile(docfile=djangofl, user=request.user, filtered=True)
        pepxmlfile.docfile.name = bname + '_PSMs.pep.xml'
        pepxmlfile.save()
        newrun.add_pepxml(pepxmlfile)
    if os.path.exists(bname + '_peptides.csv'):
        fl = open(bname + '_peptides.csv'.decode('utf-8'))
        djangofl = File(fl)
        csvf = ResCSV(docfile = djangofl, user = request.user, ftype='peptide')
        csvf.save()
        newrun.add_rescsv(csvf)
    if os.path.exists(bname + '_proteins.csv'):
        fl = open(bname + '_proteins.csv'.decode('utf-8'))
        djangofl = File(fl)
        csvf = ResCSV(docfile = djangofl, user = request.user, ftype='protein')
        csvf.save()
        newrun.add_rescsv(csvf)
    for pxml in newrun.get_pepxmlfiles():
        full = pxml.docfile.name.rsplit('.pep.xml', 1)[0] + '_full.pep.xml'
        shutil.move(pxml.docfile.name, full)
        pxml.docfile.name = full
        pxml.save()
    newrun.calc_results()
    return 1

def _runproc(request, inputfile, idsettings, newrun):
    filename = _set_pepxml_path(idsettings, inputfile)
    utils.write_pepxml(inputfile, idsettings, main.process_file(inputfile, idsettings))
    fl = open(filename, 'r')
    djangofl = File(fl)
    pepxmlfile = PepXMLFile(docfile = djangofl, user = request.user)
    pepxmlfile.docfile.name = filename
    pepxmlfile.save()
    newrun.add_pepxml(pepxmlfile)
    django.db.connection.close()
    return 1

def _start_union(request, newgroup, rn, c):
#       django.db.connection.close()
    try:
        un_run = newgroup.get_union()[0]
    except:
        un_run = False
    if un_run:
        for newrun in newgroup.get_searchruns():
            for pepf in newrun.get_pepxmlfiles():
                un_run.add_pepxml(pepf)
                un_run.save()
        _run_search(request, un_run, rn, c)

    if newgroup.get_notification():
        email_to_user(newgroup.user.email, newgroup.groupname)
    newgroup.change_status('Task finished: %s' % (time.strftime("%b %d %H:%M:%S"), ))
    django.db.connection.close()

def _start_all(request, newgroup, rn, c):
    django.db.connection.close()
    django.db.connection.ensure_connection()
#   tasker.check_user(newgroup.user)

    tmp_procs = []
    for newrun in newgroup.get_searchruns():
#       tasker.ask_for_run(newrun.user)

#        while True:
#           min_time_user = tasker.get_user_with_min_time()
#           if tasker.get_total_cursearches() < search_limit and newrun.user == min_time_user:
#               break
#           else:
#               for idx, p in enumerate(tmp_procs):
#                   if not p.is_alive():
#                       tasker.finish_run(newrun.user)
#                       tmp_procs.pop(idx)
#           time.sleep(5)

#       tasker.start_run(newrun.user)
#       p = Process(target=_run_search, args=(request, newrun, rn, c))
        p = Thread(target=_run_search, args=(request, newrun, rn, c), name='run-search')
        p.start()
        tmp_procs.append(p)
    for p in tmp_procs:
        p.join()
    p = Thread(target=_start_union, args=(request, newgroup, rn, c), name='start-union')
    p.start()
    django.db.connection.close()

def runidentipy(request):
#   django.db.connection.close()
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
#   if not os.path.exists('results'):
#       os.mkdir('results')
#   if not os.path.exists(os.path.join('results', str(request.user.id))):
#       os.mkdir(os.path.join('results', str(request.user.id)))
    c['chosenfasta'] = request.session['chosen_fasta']
    c['chosenspectra'] = request.session['chosen_spectra']
#   c['SearchForms'] = pickle.loads(request.session['bigform'])
    c['SearchForms'] = search_forms_from_request(request)
    c['paramtype'] = request.session['paramtype']
    if os.path.exists('results/%s/%s' % (str(request.user.id), c['runname'])):
        failure += 'Results with name "%s" already exist, choose another name' % c['runname']
    if not failure:
        newgroup = SearchGroup(groupname=c['runname'], user = request.user)
        newgroup.save()
        newgroup.add_files(c)
        rn = newgroup.name()
        os.makedirs('results/%s/%s' % (str(newgroup.user.id), rn.encode('utf-8')))
        newgroup.change_status('Search is running')
        t = Thread(target=_start_all, args=(request, newgroup, rn, c), name='start_all')
#       t = Process(target=start_all, args=(newgroup, rn, c))
        t.start()
        newgroup.processpid = t.ident
#       newgroup.processpid = t.pid
        newgroup.save()
        messages.add_message(request, messages.INFO, 'IdentiPy started')
        return redirect('identipy_app:getstatus')
    else:
        messages.add_message(request, messages.INFO, failure)
        return redirect('identipy_app:searchpage')

def search_details(request, pk, c={}):
#   django.db.connection.close()
    # c = {}
    runobj = get_object_or_404(SearchGroup, id=pk)
#   runobj = SearchGroup.objects.get(groupname=runname.replace(u'\xa0', ' '))
    request.session['searchgroupid'] = runobj.id
    c.update({'searchgroup': runobj})
    print runobj.id, runobj.groupname
    sruns = SearchRun.objects.filter(searchgroup_parent_id=runobj.id)
    if sruns.count() == 1:
#       return results_figure(request, sruns[0].id)
        request.session['searchrunid'] = sruns[0].id
        return redirect('identipy_app:figure', sruns[0].id)
    return render(request, 'identipy_app/results.html', c)

def results_figure(request, pk):
#   django.db.connection.close()
    c = {}
#   runobj = SearchRun.objects.get(runname=runname.replace(u'\xa0', ' '), searchgroup_parent_id=searchgroupid)
    runobj = get_object_or_404(SearchRun, id=pk)
    c.update({'searchrun': runobj, 'searchgroup': runobj.searchgroup_parent})
    return render(request, 'identipy_app/results_figure.html', c)


def showparams(request):
#   django.db.connection.close()
    c = {}
    searchgroupid = request.session.get('searchgroupid')
    runobj = SearchGroup.objects.get(id=searchgroupid, user=request.user)
    params_file = runobj.parameters.all()[0]
    raw_config = utils.CustomRawConfigParser(dict_type=dict, allow_no_value=True)
    raw_config.read(params_file.path())
    print params_file.path()

    c['SearchForms'] = {}
    for sftype in ['main'] + (['postsearch'] if c.get('paramtype', 3) == 3 else []):
        c['SearchForms'][sftype] = SearchParametersForm(raw_config=raw_config, user=request.user, label_suffix='', sftype=sftype, prefix=sftype)
    c['fastaname'] = runobj.fasta.all()[0].name()

    runobj = get_object_or_404(SearchGroup, id=searchgroupid)
    c['searchrun'] = runobj
    return render(request, 'identipy_app/params.html', c)



# def show(request, runname, searchgroupid, ftype, c, order_by_label=False, upd=False, dbname=False):
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
    runobj = SearchRun.objects.get(id=runid, searchgroup_parent_id=searchgroupid)
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
        res_dict.labelform = MultFilesForm(request.POST, custom_choices=zip(res_dict.labels, res_dict.labels), labelname=labelname, multiform=True)
        if res_dict.labelform.is_valid():
            whitelabels = [x for x in res_dict.labelform.cleaned_data.get('choices')]
            request.session[sname] = whitelabels
            res_dict.custom_labels(whitelabels)
    elif request.session.get(sname, ''):
        whitelabels = request.session.get(sname)
        res_dict.custom_labels(whitelabels)        
            # request.POST['choices'] = False
    res_dict.labelform = MultFilesForm(custom_choices=zip(res_dict.labels, res_dict.labels), labelname=labelname, multiform=True)
    res_dict.labelform.fields['choices'].initial = res_dict.get_labels()#[res_dict.labels[idx] for idx, tval in enumerate(res_dict.whiteind) if tval]
    c.update({'results_detailed': res_dict})
    runobj = SearchRun.objects.get(id=runid, searchgroup_parent_id=searchgroupid)
    c.update({'searchrun': runobj, 'searchgroup': runobj.searchgroup_parent})

    if request.GET.get('download_custom_csv', ''):
        tmpfile_name = runobj.searchgroup_parent.groupname + '_' + runobj.name() + '_' + ftype + 's_selectedfields.csv'
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
#   django.db.connection.close()
    if request.method == 'POST' and usedclass:
        cc = []
        documents = usedclass.objects.filter(user=request.user)
        for doc in documents:
            cc.append((doc.id, doc.name()))
        form = MultFilesForm(request.POST, custom_choices=cc, labelname=None)
        if form.is_valid():
            for x in form.cleaned_data.get('choices'):
                obj = usedclass.objects.get(user=request.user, id=x)
                filenames.append(obj.path())
                print obj.path()
        zip_subdir = 'down_files'
    elif request.method == 'GET':
        down_type = request.GET['down_type']
        searchgroupid = request.session.get('searchgroupid')#c['searchgroup']
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

        zip_subdir = searchgroup.name() + '_' + down_type + '_files'

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
