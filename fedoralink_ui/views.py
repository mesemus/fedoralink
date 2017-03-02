import traceback

from django.conf import settings
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.urlresolvers import resolve
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import FileResponse
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render
from django.template import Template, RequestContext
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django.utils.decorators import classonlymethod
from django.utils.translation import get_language
from django.utils.translation import ugettext as _
from django.views.generic import View, CreateView, DetailView, UpdateView

from fedoralink.authentication.Credentials import Credentials
from fedoralink.authentication.as_user import as_user
from fedoralink.fedorans import FEDORA
from fedoralink.forms import FedoraForm
from fedoralink.indexer.models import IndexableFedoraObject
from fedoralink.models import FedoraObject
from fedoralink.type_manager import FedoraTypeManager
from fedoralink_ui.template_cache import FedoraTemplateCache
from fedoralink_ui.templatetags.fedoralink_tags import id_from_path, rdf2lang

import logging

log = logging.getLogger('fedoralink_ui.views')

def appname(request):
    # print('appname: ')
    # print(request.path)
    # print(resolve(request.path).app_name)
    return {'appname': resolve(request.path).app_name}


def breadcrumbs(request, context={}, resolver_match=None, path=None, **initkwargs):
    if path.endswith('/'):
        path = path[:-1]

    if path != request.path:
        return

    obj = context['object']
    breadcrumb_list = []
    while isinstance(obj, IndexableFedoraObject):
        if obj.pk:
            object_id = id_from_path(obj.pk, initkwargs.get('fedora_prefix', None))
            if object_id:
                if hasattr(obj,"title"):
                    breadcrumb_title = rdf2lang(obj.title)
                else:
                    breadcrumb_title = object_id
                breadcrumb_list.insert(0, (
                    reverse('%s:%s' % (resolver_match.app_name, resolver_match.url_name),
                            kwargs={'id': object_id}),
                        str(breadcrumb_title)
                ))
            else:
                # reached root of the portion of repository given by fedora_prefix
                break

        parent_id = obj.fedora_parent_uri
        if parent_id:
            try:
                obj = FedoraObject.objects.get(pk=parent_id)
            except:
                # do not have rights
                break
        else:
            # reached root of the repository
            break

    return breadcrumb_list


def get_model(collection_id, fedora_prefix = None):
    if fedora_prefix:
        if collection_id:
            collection_id = fedora_prefix + '/' + collection_id
        else:
            collection_id = fedora_prefix
    model = FedoraTemplateCache.get_collection_model(FedoraObject.objects.get(pk=collection_id))
    if model is None:
        return None
    model = FedoraTypeManager.get_model_class_from_fullname(model)
    return model


def get_model_from_object(obj):
    model = FedoraTemplateCache.get_collection_model(obj)
    if model is None:
        return None
    model = FedoraTypeManager.get_model_class_from_fullname(model)
    return model


def get_subcollection_model(collection_id, fedora_prefix = None):
    if fedora_prefix:
        collection_id = fedora_prefix + '/' + collection_id
    model = FedoraTemplateCache.get_subcollection_model(FedoraObject.objects.get(pk=collection_id))
    if model is None:
        return None
    model = FedoraTypeManager.get_model_class_from_fullname(model)
    return model


def get_subcollection_model_from_object(collection_object):
    model = FedoraTemplateCache.get_subcollection_model(collection_object)
    if model is None:
        return None
    model = FedoraTypeManager.get_model_class_from_fullname(model)
    return model


class GenericIndexView(View):
    app_name = None

    # noinspection PyUnusedLocal
    def get(self, request, *args, **kwargs):
        app_name = self.app_name
        if app_name is None:
            app_name = appname(request)['appname']
        return HttpResponseRedirect(reverse(app_name + ':extended_search',
                                            kwargs={'parameters': '',
                                                    'collection_id': kwargs.get('collection_id', '')
                                                    }))


class GenericSearchView(View):
    template_name = 'fedoralink_ui/search.html'
    list_item_template = 'fedoralink_ui/search_result_row.html'
    orderings = ()
    model_class = None
    facets = None
    title = None
    create_button_title = None
    search_fields = ()
    fedora_prefix = ''

    def get(self, request, *args, **kwargs):
        try:
            return self._get(request, *args, **kwargs)
        except:
            log.exception('Exception in GenericSearchView.get(...) at path %s with params %s, %s' ,
                          request.path, args, kwargs)
            traceback.print_exc()
            raise


    # noinspection PyCallingNonCallable,PyUnresolvedReferences
    def _get(self, request, *args, **kwargs):

        if not self.model_class:
            if self.request.user.is_authenticated():
                credentials = Credentials(self.request.user.username, USERS_TOMCAT_PASSWORD)
                # print("user:" + credentials.username)
                with as_user(credentials):
                    model = get_subcollection_model(collection_id=kwargs['collection_id'], fedora_prefix=self.fedora_prefix)
            else:
                model = get_subcollection_model(collection_id=kwargs['collection_id'], fedora_prefix=self.fedora_prefix)
        else:
            model = self.model_class

        if self.facets and callable(self.facets):
            requested_facets = self.facets(request)
        else:
            requested_facets = self.facets

        within_collection = None
        if 'path' in kwargs:
            within_collection = FedoraObject.objects.get(pk=kwargs['path'])

        requested_facet_ids = [x[0] for x in requested_facets]

        data = model.objects.all()

        if requested_facets:
            data = data.request_facets(*requested_facet_ids)

        if 'searchstring' in request.GET and request.GET['searchstring'].strip():
            q = None
            for fld in self.search_fields:
                q1 = Q(**{fld + "__fulltext": request.GET['searchstring'].strip()})
                if q:
                    q |= q1
                else:
                    q = q1
            data = data.filter(q)

        for k in request.GET:
            if k.startswith('facet__'):
                values = request.GET.getlist(k)
                k = k[len('facet__'):]
                q = None
                for v in values:
                    if not q:
                        q = Q(**{k: v})
                    else:
                        q |= Q(**{k: v})
                if q:
                    data = data.filter(q)

        if within_collection:
            data = data.filter(_fedora_parent__exact=within_collection.id)

        current_language = get_language()

        sort = request.GET.get('sort', self.orderings[0][0])
        if sort:
            data = data.order_by(*[x.strip().replace('@lang', '@' + current_language) for x in sort.split(',')])
        page = request.GET.get('page', )
        paginator = Paginator(data, 10)

        try:
            page = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            page = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            page = paginator.page(paginator.num_pages)

        template = None
        if 'path' in kwargs:
            template = FedoraTemplateCache.get_template_string(within_collection,
                                                               'search')

        if not template:
            template = get_template(self.template_name)

        context = RequestContext(request, {
            'page': page,
            'data': data,
            'item_template': self.list_item_template,
            'facet_names': {k: v for k, v in requested_facets},
            'searchstring': request.GET.get('searchstring', ''),
            'orderings': self.orderings,
            'ordering': sort,
            'title': self.title,
            'create_button_title': self.create_button_title,
            'fedora_prefix': self.fedora_prefix
        })

        return TemplateResponse(request, template, context)

# def show_urls(urllist, depth=0):
#     for entry in urllist:
#         print("url entry: ", "  " * depth, entry.regex.pattern, entry.callback if hasattr(entry, 'callback') else '')
#         if hasattr(entry, 'url_patterns'):
#             show_urls(entry.url_patterns, depth + 1)


# noinspection PyAttributeOutsideInit,PyProtectedMember
class GenericDetailView(DetailView):
    template_name = 'fedoralink_ui/detail.html'
    fedora_prefix = None
    pk_url_kwarg = 'id'
    always_use_indexer = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object = None

    def use_indexer(self):
        if callable(self.always_use_indexer):
            return self.always_use_indexer(self.request)
        return self.always_use_indexer

    def get_queryset(self):
        ret = FedoraObject.objects.all()
        if self.use_indexer():
            ret = ret.via_indexer()
        return ret

    def get_object(self, queryset=None):
        if self.object:
            return self.object

        print("path: ", self.request.path)
        # import cis_repo.urls
        # show_urls(cis_repo.urls.urlpatterns)
        pk = self.kwargs.get(self.pk_url_kwarg, "").replace("_", "/")
        if self.fedora_prefix and 'prefix_applied' not in self.kwargs:
            pk = self.fedora_prefix + '/' + pk
            self.kwargs['prefix_applied'] = True
        if pk.endswith('/'):
            pk = pk[:-1]

        if self.use_indexer():
            repo_url = settings.DATABASES['repository']['REPO_URL']
            if pk[:1] != '/' and not repo_url.endswith('/'):
                pk = '/' + pk
            pk = repo_url + pk

        self.kwargs[self.pk_url_kwarg] = pk
        self.object = super().get_object(queryset)
        # if not isinstance(retrieved_object, IndexableFedoraObject):
        #     raise Exception("Can not use object with pk %s in a generic view as it is not of a known type" % pk)
        from fedoralink_ui.generic_urls import cache_breadcrumbs
        cache_breadcrumbs(self.object)
        return self.object

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if (FEDORA.Binary in self.object.types):
            bitstream = self.object.get_bitstream()
            resp = FileResponse(bitstream.stream, content_type=bitstream.mimetype)
            resp['Content-Disposition'] = 'inline; filename="%s"' % bitstream.filename
            return resp
        # noinspection PyTypeChecker
        template = FedoraTemplateCache.get_template_string(self.object, view_type='view')
        if template:
            context = self.get_context_data(object=self.object)
            return HttpResponse(
                Template("{% extends '" + self.template_name + "' %}" + template).render(
                    RequestContext(request, context)))
        return super(GenericDetailView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fedora_prefix'] = self.fedora_prefix
        context['model'] = get_model_from_object(self.get_object())
        context['subcollection_model'] = get_subcollection_model_from_object(self.get_object())
        return context

    @classonlymethod
    def as_view(cls, **initkwargs):
        ret = super().as_view(**initkwargs)
        ret.urlbreadcrumbs_verbose_name = breadcrumbs
        return ret


class GenericCreateView(CreateView):
    fields = '__all__'
    pk_url_kwarg = 'id'
    # TODO: parent_collection nebude potrebny, moznost ziskat z url
    parent_collection = None
    success_url_param_names = ()
    template_name = 'fedoralink_ui/create.html'
    fedora_prefix = None

    def form_valid(self, form):
        inst = form.save(commit=False)
        inst.save()
        self.object = inst
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        parent = self.get_parent_object()
        if parent is None:
            if callable(self.parent_collection):
                parent = self.parent_collection(self)
            else:
                parent = self.parent_collection
        model = get_model(collection_id=self.kwargs.get('id'), fedora_prefix=self.fedora_prefix)
        self.object = ret['instance'] = parent.create_child('', flavour=model)

        return ret

    def get_queryset(self):
        return FedoraObject.objects.all()

    # noinspection PyUnusedLocal,PyProtectedMember
    def get_parent_object(self, queryset=None):
        """
        Returns the object the view is displaying.

        By default this requires `self.queryset` and a `pk` or `slug` argument
        in the URL conf, but subclasses can override this to return any object.
        """
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        queryset = self.get_queryset()

        # Next, try looking up by primary key.
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        if pk is not None:
            queryset = queryset.filter(pk=(self.fedora_prefix+"/"+pk) if self.fedora_prefix else pk)

            try:
                # Get the single item from the filtered queryset
                obj = queryset.get()
            except queryset.model.DoesNotExist:
                raise Http404(_("No %(verbose_name)s found matching the query") %
                              {'verbose_name': queryset.model._meta.verbose_name})
            return obj
        else:
            return None

    def get_form_class(self):
        # print(self.kwargs)
        model = get_model(collection_id=self.kwargs.get('id'), fedora_prefix=self.fedora_prefix)
        meta = type('Meta', (object, ), {'model': model, 'fields': '__all__'})
        return type(model.__name__ + 'Form', (FedoraForm,), {
            'Meta': meta
        })

    @classonlymethod
    def as_view(cls, **initkwargs):
        ret = super().as_view(**initkwargs)
        def breadcrumbs(request, context={}, resolver_match=None, path=None):
            if path.endswith('/'):
                path = path[:-1]

            if path != request.path:
                return

            obj = context['object']
            breadcrumb_list = []
            while isinstance(obj, IndexableFedoraObject):
                object_id = id_from_path(obj.pk, initkwargs.get('fedora_prefix', None))
                if object_id:
                    breadcrumb_list.insert(0, (
                        reverse('%s:%s' % (resolver_match.app_name, resolver_match.url_name),
                                kwargs={'id': object_id}),
                        str(rdf2lang(obj.title))
                    ))
                else:
                    # reached root of the portion of repository given by fedora_prefix
                    break

                parent_id = obj.fedora_parent_uri
                if parent_id:
                    obj = FedoraObject.objects.get(pk=parent_id)
                else:
                    # reached root of the repository
                    break

            return breadcrumb_list
        ret.urlbreadcrumbs_verbose_name = breadcrumbs
        return ret

    # noinspection PyProtectedMember
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response, using the `response_class` for this
        view, with a template rendered with the given context.

        If any keyword arguments are provided, they will be
        passed to the constructor of the response class.
        """
        model = get_model(self.kwargs.get('id'), fedora_prefix=self.fedora_prefix)
        template = FedoraTemplateCache.get_template_string(self.object if self.object else model,
                                                           view_type='create')
        if template:
            return HttpResponse(
                Template("{% extends '" + self.template_name + "' %}" + template).render(
                    RequestContext(self.request, context)))
        return super().render_to_response(context, **response_kwargs)

    def get_success_url(self):
        return reverse(self.success_url,
                       kwargs={k: _convert(k, getattr(self.object, k), self.fedora_prefix) for k in
                               self.success_url_param_names})

class GenericSubcollectionCreateView(CreateView):
    fields = '__all__'
    pk_url_kwarg = 'id'
    # TODO: parent_collection nebude potrebny, moznost ziskat z url
    parent_collection = None
    success_url_param_names = ()
    template_name = 'fedoralink_ui/create.html'
    fedora_prefix = None

    def form_valid(self, form):
        inst = form.save(commit=False)
        inst.save()
        self.object = inst
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        parent = self.get_parent_object()
        if parent is None:
            if callable(self.parent_collection):
                parent = self.parent_collection(self)
            else:
                parent = self.parent_collection
        model = get_subcollection_model(collection_id=self.kwargs.get('id'), fedora_prefix=self.fedora_prefix)
        self.object = ret['instance'] = parent.create_child('', flavour=model)

        return ret

    def get_queryset(self):
        return FedoraObject.objects.all()

    # noinspection PyUnusedLocal,PyProtectedMember
    def get_parent_object(self, queryset=None):
        """
        Returns the object the view is displaying.

        By default this requires `self.queryset` and a `pk` or `slug` argument
        in the URL conf, but subclasses can override this to return any object.
        """
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        queryset = self.get_queryset()

        # Next, try looking up by primary key.
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        if pk is not None:
            if (self.fedora_prefix):
                queryset = queryset.filter(pk=self.fedora_prefix+"/"+pk)
            else:
                queryset = queryset.filter(pk=pk)
            try:
                # Get the single item from the filtered queryset
                obj = queryset.get()
            except queryset.model.DoesNotExist:
                raise Http404(_("No %(verbose_name)s found matching the query") %
                              {'verbose_name': queryset.model._meta.verbose_name})
            return obj
        else:
            return None

    def get_form_class(self):
        # print(self.kwargs)
        model = get_subcollection_model(collection_id=self.kwargs.get('id'), fedora_prefix=self.fedora_prefix)
        meta = type('Meta', (object, ), {'model': model, 'fields': '__all__'})
        return type(model.__name__ + 'Form', (FedoraForm,), {
            'Meta': meta
        })

    @classonlymethod
    def as_view(cls, **initkwargs):
        ret = super().as_view(**initkwargs)
        def breadcrumbs(request, context={}, resolver_match=None, path=None):
            if path.endswith('/'):
                path = path[:-1]

            if path != request.path:
                return

            obj = context['object']
            breadcrumb_list = []
            while isinstance(obj, IndexableFedoraObject):
                object_id = id_from_path(obj.pk, initkwargs.get('fedora_prefix', None))
                if object_id:
                    breadcrumb_list.insert(0, (
                        reverse('%s:%s' % (resolver_match.app_name, resolver_match.url_name),
                                kwargs={'id': object_id}),
                        str(rdf2lang(obj.title))
                    ))
                else:
                    # reached root of the portion of repository given by fedora_prefix
                    break

                parent_id = obj.fedora_parent_uri
                if parent_id:
                    obj = FedoraObject.objects.get(pk=parent_id)
                else:
                    # reached root of the repository
                    break

            return breadcrumb_list
        ret.urlbreadcrumbs_verbose_name = breadcrumbs
        return ret

    # noinspection PyProtectedMember
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response, using the `response_class` for this
        view, with a template rendered with the given context.

        If any keyword arguments are provided, they will be
        passed to the constructor of the response class.
        """
        model = get_subcollection_model(self.kwargs.get('id'), fedora_prefix=self.fedora_prefix)
        template = FedoraTemplateCache.get_template_string(self.object if self.object else model,
                                                           view_type='create')
        if template:
            return HttpResponse(
                Template("{% extends '" + self.template_name + "' %}" + template).render(
                    RequestContext(self.request, context)))
        return super().render_to_response(context, **response_kwargs)

    def get_success_url(self):
        return reverse(self.success_url,
                       kwargs={k: _convert(k, getattr(self.object, k), self.fedora_prefix) for k in
                               self.success_url_param_names})


class GenericEditView(UpdateView):
    fields = '__all__'
    success_url_param_names = ('id',)
    template_name = 'fedoralink_ui/edit.html'
    pk_url_kwarg = 'id'
    fedora_prefix = None

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg, None).replace("_", "/")

        if self.fedora_prefix and 'prefix_applied' not in self.kwargs:
            pk = self.fedora_prefix + '/' + pk
            self.kwargs['prefix_applied'] = True
        self.kwargs[self.pk_url_kwarg] = pk
        retrieved_object = super().get_object(queryset)
        if not isinstance(retrieved_object, IndexableFedoraObject):
            raise Exception("Can not use object with pk %s in a generic view as it is not of a known type" % pk)
        return retrieved_object

    def get_form_class(self):
        # fedora_prefix already added to pk
        if self.object:
            model = type(self.object)
        else:
            model = get_model(self.kwargs.get(self.pk_url_kwarg))

        meta = type('Meta', (object,), {'model': model, 'fields': '__all__'})
        return type(model.__name__ + 'Form', (FedoraForm,), {
            'Meta': meta
        })

    # noinspection PyAttributeOutsideInit,PyProtectedMember
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response, using the `response_class` for this
        view, with a template rendered with the given context.

        If any keyword arguments are provided, they will be
        passed to the constructor of the response class.
        """
        self.object = self.get_object()
        form = self.get_form()
        # print("media", form.media)
        context = self.get_context_data(object=self.object, form=form, **response_kwargs)
        # noinspection PyTypeChecker
        template = FedoraTemplateCache.get_template_string(self.object, view_type='edit')

        if template:
            return HttpResponse(
                Template("{% extends '" + self.template_name + "' %}" + template).render(
                    RequestContext(self.request, context)))
        return super().render_to_response(context, **response_kwargs)

    def get_success_url(self):
        return reverse(self.success_url,
                       kwargs={k: _convert(k, getattr(self.object, k), self.fedora_prefix) for k in self.success_url_param_names})


def _convert(name, value, fedora_prefix=None):
    if name == 'pk' or name == 'id':
        return id_from_path(value, fedora_prefix=fedora_prefix)
    return value


def link_choose(request, model_name):
    model = FedoraTypeManager.get_model_class_from_fullname(model_name)
    data = model.objects.all()

    page = request.GET.get('page', )
    paginator = Paginator(data, 10)

    try:
        page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.page(paginator.num_pages)

    context = RequestContext(request, {
        'page': page,
        'data': data,
        'fedora_prefix': None,
        'searchstring': request.GET.get('searchstring', ''),
    })

    return render(request, 'fedoralink_ui/link_dialog_content.html', context)


def link_detail(request, pk):
    object = FedoraObject.objects.get(pk=pk)
    return render(request, 'fedoralink_ui/link_dialog_done.html', locals())
