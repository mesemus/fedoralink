import inspect
import requests
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.template import Template, RequestContext
from django.utils.translation import ugettext as _
from django.views.generic import View, CreateView, DetailView, UpdateView

from fedoralink.forms import FedoraForm
from fedoralink.indexer.models import IndexableFedoraObject
from fedoralink.models import FedoraObject
from fedoralink_ui.templatetags.fedoralink_tags import id_from_path
from fedoralink_ui.models import ResourceType
from .utils import get_class, fullname


class GenericGetView():
    def getChildTemplate(self, type, templateType):
        # TODO: more templates
        if templateType == 'edit' or templateType == 'create':
            return FedoraObject.objects.filter(
                pk=type.templates_edit[0]).get()
        if templateType == 'view':
            return FedoraObject.objects.filter(
                pk=type.templates_view[0]).get()

    def get(self, rdf_meta, templateType):
        for rdf_type in rdf_meta:
            retrieved_type = list(ResourceType.objects.filter(rdf_types=rdf_type))
            if retrieved_type: break
        template_url = None
        for type in retrieved_type:
            if ('type/' in type.id):
                child = self.getChildTemplate(type=type, templateType=templateType)
                for template in child.children:
                    template_url = template.id
        return template_url


class GenericIndexView(View):
    app_name = None

    def get(self, request):
        return HttpResponseRedirect(reverse(self.app_name + ':rozsirene_hledani', kwargs={'parametry': ''}))


# noinspection PyUnresolvedReferences
class FedoraTemplateMixin:
    def get_template_names(self):
        if self.object:
            templates = [fullname(x).replace('.', '/') + '/_' + self.template_type + '.html'
                         for x in inspect.getmro(type(self.object))]
            templates.append(self.template_name)
            return templates
        return super().get_template_names()


class GenericDownloadView(View):
    model = None

    def get(self, request, bitstream_id):
        attachment = self.model.objects.get(pk=bitstream_id.replace('_', '/'))
        bitstream = attachment.get_bitstream()
        resp = FileResponse(bitstream.stream, content_type=bitstream.mimetype)
        resp['Content-Disposition'] = 'inline; filename="' + attachment.filename
        return resp


class GenericChangeStateView(View):
    model = None

    def post(self, request, pk):
        raise Exception("Not implemented yet ...")


class GenericIndexerView(View):
    model = FedoraObject
    template_name = 'fedoralink_ui/indexer_view.html'
    list_item_template = 'fedoralink_ui/indexer_resource_view.html'
    orderings = ()
    default_ordering = ''
    facets = None
    title = None
    create_button_title = None

    # noinspection PyCallingNonCallable
    def get(self, request, parametry):
        if isinstance(self.model, str):
            self.model = get_class(self.model)

        if self.facets and callable(self.facets):
            requested_facets = self.facets(request, parametry)
        else:
            requested_facets = self.facets

        requested_facet_ids = [x[0] for x in requested_facets]

        data = self.model.objects.all()

        if requested_facets:
            data = data.request_facets(*requested_facet_ids)

        if 'searchstring' in request.GET and request.GET['searchstring'].strip():
            data = data.filter(solr_all_fields=request.GET['searchstring'].strip())

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

        sort = request.GET.get('sort', self.default_ordering or self.orderings[0][0])
        if sort:
            data = data.order_by(*[x.strip() for x in sort.split(',')])
        page = request.GET.get('page')
        paginator = Paginator(data, 10)

        try:
            page = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            page = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            page = paginator.page(paginator.num_pages)

        return render(request, self.template_name, {
            'page': page,
            'data': data,
            'item_template': self.list_item_template,
            'facet_names': {k: v for k, v in requested_facets},
            'searchstring': request.GET.get('searchstring', ''),
            'orderings': self.orderings,
            'ordering': sort,
            'title': self.title,
            'create_button_title': self.create_button_title
        })


class GenericLinkTitleView(DetailView, FedoraTemplateMixin):
    prefix = None
    template_name = None

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_object(self, queryset=None):
        pk = self.prefix + self.kwargs.get(self.pk_url_kwarg, None).replace("_", "/")
        self.kwargs[self.pk_url_kwarg] = pk
        retrieved_object = super().get_object(queryset)
        if not isinstance(retrieved_object, IndexableFedoraObject):
            raise Exception("Can not use object with pk %s in a generic view as it is not of a known type" % pk)
        return retrieved_object


class GenericLinkView(View):
    model = FedoraObject
    template_name = 'fedoralink/link_view.html'
    base_template = 'please_set_base_template_for_generic_link_view'
    list_item_template = 'please_set_item_template_for_generic_link_view'
    orderings = ()
    default_ordering = ''
    facets = None
    title = None
    create_button_title = None

    # noinspection PyCallingNonCallable
    def get(self, request, parametry):
        if isinstance(self.model, str):
            self.model = get_class(self.model)

        if self.facets and callable(self.facets):
            requested_facets = self.facets(request, parametry)
        else:
            requested_facets = self.facets

        requested_facet_ids = [x[0] for x in requested_facets]

        data = self.model.objects.all()

        if requested_facets:
            data = data.request_facets(*requested_facet_ids)

        if 'searchstring' in request.GET and request.GET['searchstring'].strip():
            data = data.filter(solr_all_fields=request.GET['searchstring'].strip())

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

        sort = request.GET.get('sort', self.default_ordering or self.orderings[0][0])
        if sort:
            data = data.order_by(*[x.strip() for x in sort.split(',')])
        page = request.GET.get('page')
        paginator = Paginator(data, 10)

        try:
            page = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            page = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            page = paginator.page(paginator.num_pages)

        return render(request, self.template_name, {
            'page': page,
            'data': data,
            'base_template': self.base_template,
            'item_template': self.list_item_template,
            'facet_names': {k: v for k, v in requested_facets},
            'searchstring': request.GET.get('searchstring', ''),
            'orderings': self.orderings,
            'ordering': sort,
            'title': self.title,
            'create_button_title': self.create_button_title
        })


class GenericDetailView(DetailView, FedoraTemplateMixin):
    prefix = None
    template_name = None
    template_type = 'detail'
    base_template = 'fedoralink_ui/detail.html'

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_object(self, queryset=None):
        pk = self.prefix + self.kwargs.get(self.pk_url_kwarg, None).replace("_", "/")
        self.kwargs[self.pk_url_kwarg] = pk
        retrieved_object = super().get_object(queryset)
        if not isinstance(retrieved_object, IndexableFedoraObject):
            raise Exception("Can not use object with pk %s in a generic view as it is not of a known type" % pk)
        return retrieved_object

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        getView = GenericGetView()
        template_url = getView.get(rdf_meta=self.object._meta.rdf_types, templateType='view')
        # print(template_url)
        if template_url:
            return HttpResponse(
                Template("{% extends '" + self.base_template + "' %}" + requests.get(template_url).text).render(
                    RequestContext(request, context)))
        return super(GenericDetailView, self).get(request, *args, **kwargs)


class GenericEditView(UpdateView, FedoraTemplateMixin):
    model = None
    fields = '__all__'
    template_name = None
    template_type = 'edit'
    prefix = None
    template_name_suffix = None
    success_url_param_names = ()
    title = None
    base_template = 'fedoralink_ui/edit.html'

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_object(self, queryset=None):
        pk = self.prefix + self.kwargs.get(self.pk_url_kwarg, None).replace("_", "/")
        self.kwargs[self.pk_url_kwarg] = pk
        retrieved_object = super().get_object(queryset)
        if not isinstance(retrieved_object, IndexableFedoraObject):
            raise Exception("Can not use object with pk %s in a generic view as it is not of a known type" % pk)
        return retrieved_object

    def get_form_class(self):
        meta = type('Meta', (object,), {'model': self.model, 'fields': '__all__'})
        return type(self.model.__name__ + 'Form', (FedoraForm,), {
            'Meta': meta
        })

    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response, using the `response_class` for this
        view, with a template rendered with the given context.

        If any keyword arguments are provided, they will be
        passed to the constructor of the response class.
        """
        self.object = self.get_object()
        form = self.get_form()
        context = self.get_context_data(object=self.object, form=form, **response_kwargs)
        getView = GenericGetView()
        template_url = getView.get(rdf_meta=self.object._meta.rdf_types, templateType='edit')
        # print(template_url)
        if template_url:
            return HttpResponse(
                Template("{% extends '" + self.base_template + "' %}" + requests.get(template_url).text).render(
                    RequestContext(self.request, context)))
        return super().render_to_response(context, **response_kwargs)

    def get_success_url(self):
        return reverse(self.success_url,
                       kwargs={k: _convert(k, getattr(self.object, k)) for k in self.success_url_param_names})


# noinspection PyAttributeOutsideInit,PyCallingNonCallable
class GenericDocumentCreate(CreateView, FedoraTemplateMixin):
    model = None
    fields = '__all__'
    template_name = None
    parent_collection = None
    success_url_param_names = ()
    title = None
    base_template = 'fedoralink_ui/create.html'

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

        self.object = ret['instance'] = parent.create_child('', flavour=self.model)

        return ret

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_parent_object(self, queryset=None):
        """
        Returns the object the view is displaying.

        By default this requires `self.queryset` and a `pk` or `slug` argument
        in the URLconf, but subclasses can override this to return any object.
        """
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        queryset = self.get_queryset()

        # Next, try looking up by primary key.
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        if pk is not None:
            pk=pk.replace("_", "/")
            queryset = queryset.filter(pk=pk)

            try:
                # Get the single item from the filtered queryset
                obj = queryset.get()
            except queryset.model.DoesNotExist:
                raise Http404(_("No %(verbose_name)s found matching the query") %
                              {'verbose_name': queryset.model._meta.verbose_name})
            return obj
        else: return None

    def get_form_class(self):
        meta = type('Meta', (object, ), {'model': self.model, 'fields': '__all__'})
        return type(self.model.__name__ + 'Form', (FedoraForm,), {
            'Meta': meta
        })

    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response, using the `response_class` for this
        view, with a template rendered with the given context.

        If any keyword arguments are provided, they will be
        passed to the constructor of the response class.
        """
        if self.object:
            rdf_meta = self.object._meta.rdf_types
        else:
            rdf_meta = self.model._meta.rdf_types
        getView = GenericGetView()
        template_url = getView.get(rdf_meta=rdf_meta, templateType='create')
        if template_url:
            return HttpResponse(
                Template("{% extends '" + self.base_template + "' %}" + requests.get(template_url).text).render(
                    RequestContext(self.request, context)))
        return super().render_to_response(context, **response_kwargs)

    def get_success_url(self):
        return reverse(self.success_url,
                       kwargs={k: _convert(k, getattr(self.object, k)) for k in self.success_url_param_names})


def _convert(name, value):
    if name == 'pk' or name == 'id':
        return id_from_path(value)
    return value


class ModelViewRegistry:
    views = {}

    @classmethod
    def register_view(cls, model, view_type, app_name, view_name):
        cls.views[(model, view_type)] = app_name + ':' + view_name

    @classmethod
    def get_view(cls, model, view_type):
        for model_cls in inspect.getmro(model):
            r = cls.views.get((model_cls, view_type), None)
            if r is not None:
                return r
        raise Exception('View for %s, %s is not registered. Use ModelViewRegistry.register_view to register it.' % (
            model, view_type))
