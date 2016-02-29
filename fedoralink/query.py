import copy
from django.db.models import Q


class LazyFedoraQuery:
    """
    Lazy query, gets evaluated as late as possible
    """

    def __init__(self, manager, current_connection=None, filter_set=None, using='repository', do_fetch_child_metadata=True):
        """
        creates a new query from a given manager

        :param manager:     the manager
        :return:            new query
        """
        self.manager                = manager
        self.current_connection     = None
        self.__filter_set           = filter_set
        self.__using                = using
        self.__fetch_child_metadata = do_fetch_child_metadata
        self.__start = 0
        self.__end   = None
        self.__executed_data = None
        self.__request_facets = None
        self.__orderby = None
        self.__values = None
        self.model = manager._model_class
        self.model.DoesNotExist = DoesNotExist

    def get(self, **kwargs):
        """
        returns a single object fulfilling the query parameters

        :param kwargs:      list of query params, same as those that would go to filter(...)
        :return:            instance of the object
        :raise MultipleObjectsReturned   if multiple objects would have been returned
        :raise DoesNotExist              if there is no such object
        """
        query = self.filter(**kwargs)
        answer = query.execute()
        ret = None
        for a in answer:
            if ret is None:
                ret = a
            else:
                raise MultipleObjectsReturned()
        if ret is None:
            raise DoesNotExist()
        return ret

    def filter(self, *args, **kwargs):
        """
        Filters the current set of resources

        :param kwargs: Supported parameters (for now)
                        pk      identifier of the resource
        :return:       lazy set of resources
        """

        ret = copy.copy(self)

        q = None
        for a in args:
            if q is None:
                q = a
            else:
                q &= a

        if q:
            q &= Q(**kwargs)
        else:
            q = Q(**kwargs)

        if q:
            if self.__filter_set is None:
                ret.__filter_set = q
                return ret
            ret.__filter_set = self.__filter_set & q

        return ret

    def using(self, using):
        """
        Sets the repository which should be queried. If not used, defaults to 'repository' (as defined in settings.py),
        section 'DATABASES'

        :param using:   the label of the new repository
        :return:        new query with the repository set up
        """
        ret = copy.copy(self)
        ret.__using = using
        return ret

    def order_by(self, *ordering):

        ret = copy.copy(self)

        if not ordering:
            ret.__orderby = None
            return ret

        if ret.__orderby is None:
            ret.__orderby = []
        ret.__orderby.extend(ordering)

        return ret

    def request_facets(self, *facets):
        """
        When the query is executed, the response will contain a list of tuples (in the same order as requested facets)
        ( facet name, list of tuples (value, count)) where the inner list of tuples is ordered by count desc.

        :param facets: the facets requested
        :return: query object
        """
        ret = copy.copy(self)
        ret.__request_facets = facets
        return ret

    def all(self):
        ret = copy.copy(self)
        ret.__filter_set = None
        return ret

    def fetch_child_metadata(self, do_fetch_child_metadata=True):
        ret = copy.copy(self)
        ret.__fetch_child_metadata = do_fetch_child_metadata
        return ret

    def __getitem__(self, item):
        ret = copy.copy(self)
        if isinstance(item, slice):
            if item.start is None:
                ret._start = 0
            else:
                ret.__start = item.start
            ret.__end   = item.stop
            if item.step is not None and item.step != 1:
                raise AttributeError('Step is not supported in slice')
        else:
            ret.__start = item
            ret.__end   = item + 1
        return ret

    def count(self):
        return self[0:0].execute().count()

    @property
    def facets(self):
        if self.__executed_data or self.__end is not None:
            return self.execute().facets
        else:
            # if not executed, can not risk returning the whole set, so call with zero row count and
            # do not store the result
            return copy.copy(self)[0:0].execute().facets

    def execute(self):
        """
        Executes the query. Normally there is no reason to do this, because .get() or __iter__ takes care of this
        :return:    generator returning the fetched values
        """
        if self.__executed_data:
            return self.__executed_data

        self.current_connection = self.manager.connection

        repository_pk = self._get_repository_pk()
        if repository_pk is not None:
            if self.__values:
                raise Exception('values() are not yet implemented on .get(pk=)/.filter(pk=)')

            self.__executed_data = QueryData(self.manager, 1, [(x, {}) for x in self.current_connection.get_object(repository_pk,
                                                fetch_child_metadata=self.__fetch_child_metadata)])
        else:
            # call search engine
            search_response = self.manager.get_indexer(self.__using).search(self.__filter_set,
                                                                            self.model,
                                                                            self.__start, self.__end,
                                                                            self.__request_facets,
                                                                            self.__orderby,
                                                                            self.__values)

            self.__executed_data = QueryData(self.manager, search_response['count'],
                                             search_response['data'], incomplete=True,
                                             facets = search_response['facets'],
                                             values=self.__values)

        return self.__executed_data

    def values(self, *_values):
        ret = copy.copy(self)
        ret.__values = _values
        return ret

    def _get_repository_pk(self):
        """
        Internal method. If the query contains only pk, returns it (can call repository directly), otherwise
        return None (will direct to search engine - solr)

        :return:    non-null if there is only pk, otherwise None
        """
        if self.__filter_set is None:
            return None                     # call indexer to get all objects of the target type

        if len(self.__filter_set.children) > 1:
            return None

        # if there is only one child and it is a tuple, check if its name is 'pk'. If so, return the value
        if isinstance(self.__filter_set.children[0], tuple) and \
                        self.__filter_set.children[0][0] == 'pk' and \
                        len(self.__filter_set.children) == 1:

            return self.__filter_set.children[0][1]

        # otherwise it is not a simple query and go through the indexer ...
        return None

    def __iter__(self):
        for r in self.execute():
            yield r

    def __len__(self):
        return len(self.execute())


class DoesNotExist(Exception):
    """
    Exception thrown in .get if resource does not exist
    """
    pass


class MultipleObjectsReturned(Exception):
    """
    Exception thrown in .get if multiple objects would have been returned
    """
    pass


class QueryData:

    def __init__(self, manager, count, raw_data, incomplete=False, facets=None, values=None):
        if not facets:
            facets = {}
        self.manager   = manager
        self._count    = count
        self._incomplete = incomplete
        self.facets = facets
        self.data = []
        if values is None:
            for x in raw_data:
                d = self._construct(x[0])
                d._highlighted = x[1]
                self.data.append(d)
        else:
            self.data.extend(raw_data)

    def _construct(self, x):
        x = self.manager.construct(x)
        x.is_incomplete = self._incomplete
        return x

    def __iter__(self):
        return iter(self.data)

    def count(self):
        return self._count

    def __len__(self):
        return len(self.data)