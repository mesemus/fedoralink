from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.shortcuts import render
from django.views.generic import View
from .utils import get_class


class GenericIndexerView(View):

    model_class   = 'fedoralink.models.FedoraObject'
    template_name = 'fedoralink/indexer_view.html'
    base_template = 'please_set_base_template_for_generic_indexer_view'
    list_item_template = 'please_set_base_template_for_generic_indexer_view'
    orderings = ()
    default_ordering = ''
    facets = None

    def get(self, request, parametry):
        if isinstance(self.model_class, str):
            self.model_class = get_class(self.model_class)

        if self.facets and callable(self.facets):
            requested_facets = self.facets(request, parametry)
        else:
            requested_facets = self.facets

        requested_facet_ids   = [x[0] for x in requested_facets]
        requested_facet_names = [x[1] for x in requested_facets]

        data = self.model_class.objects.all()

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
                        q = Q(**{k : v})
                    else:
                        q |= Q(**{k : v})
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
            'page' : page,
            'data' : data,
            'base_template' : self.base_template,
            'item_template' : self.list_item_template,
            'facet_names'   : {k : v for k, v in requested_facets},
            'searchstring'  : request.GET.get('searchstring', ''),
            'orderings'     : self.orderings,
            'ordering'      : sort
        })

