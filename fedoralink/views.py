import inspect

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse
from django.shortcuts import render
from django.views.generic import View, CreateView, DetailView, UpdateView

from fedoralink.models import FedoraObject
from .utils import get_class, fullname


class GenericIndexView(View):
    app_name = None

    def get(self, request):
        return HttpResponseRedirect(reverse(self.app_name + ':rozsirene_hledani', kwargs={'parametry': ''}))

class FedoraTemplateMixin():
    def get_template_names(self):
        if self.object:
            templates = [fullname(x).replace('.', '/') + '/_'+self.template_type+'.html' for x in inspect.getmro(type(self.object))]
            templates.append(self.template_name)
            return templates
        return super(GenericDetailView, self).get_template_names()


class GenericDownloadView(View):
    model = None

    def get(self, request, bitstream_id):
        attachment = self.model.objects.get(pk=bitstream_id.replace('_', '/'))
        bitstream = attachment.get_bitstream()
        resp = FileResponse(bitstream.stream, content_type=bitstream.mimetype)
        resp['Content-Disposition'] = 'inline; filename="' + attachment.filename
        return resp


class GenericIndexerView(View):
    model = FedoraObject
    template_name = 'fedoralink/indexer_view.html'
    base_template = 'please_set_base_template_for_generic_indexer_view'
    list_item_template = 'please_set_base_template_for_generic_indexer_view'
    orderings = ()
    default_ordering = ''
    facets = None

    def get(self, request, parametry):
        if isinstance(self.model, str):
            self.model = get_class(self.model)

        if self.facets and callable(self.facets):
            requested_facets = self.facets(request, parametry)
        else:
            requested_facets = self.facets

        requested_facet_ids = [x[0] for x in requested_facets]
        requested_facet_names = [x[1] for x in requested_facets]

        data = self.model.objects.all()

        if requested_facets:
            data = data.request_facets(*requested_facet_ids)

        if 'searchstring' in request.GET and request.GET['searchstring'].strip():
            data = data.filter(solr_all_fields=request.GET['searchstring'].strip())

        for k in request.GET:
            if k.startswith('facet__'):
                vals = request.GET.getlist(k)
                k = k[len('facet__'):]
                q = None
                for v in vals:
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
            'ordering': sort
        })


class GenericDocumentCreate(CreateView, FedoraTemplateMixin):
    model = None
    fields = '__all__'
    template_name = None
    parent_collection = None

    def form_valid(self, form):
        inst = form.save(commit=False)
        inst.save()
        self.object = inst

        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()

        if callable(self.parent_collection):
            parent = self.parent_collection(self)
        else:
            parent = self.parent_collection

        self.object = ret['instance'] = parent.create_child('', flavour=self.model)

        return ret


class GenericDetailView(DetailView, FedoraTemplateMixin):
    prefix = None
    template_name = None
    template_type = 'detail'

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_object(self, queryset=None):
        pk = self.prefix + self.kwargs.get(self.pk_url_kwarg, None).replace("_", "/")
        self.kwargs[self.pk_url_kwarg] = pk
        print(self.kwargs)
        return super().get_object(queryset)




class GenericEditView(UpdateView, FedoraTemplateMixin):
    fields = '__all__'
    template_name = None
    template_type = 'edit'

    prefix = None

    def get_queryset(self):
        return FedoraObject.objects.all()

    def get_object(self, queryset=None):
        pk = self.prefix + self.kwargs.get(self.pk_url_kwarg, None).replace("_", "/")
        self.kwargs[self.pk_url_kwarg] = pk
        print(self.kwargs)
        return super().get_object(queryset)
