import logging
log = logging.getLogger('fedoralink.indexer')


class Indexer:
    # abstract method
    def search(self, query, model_class, start, end, facets, ordering, values):
        raise Exception("Please reimplement this method in inherited classes")