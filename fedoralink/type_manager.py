import inspect
from fedoralink.fedorans import RDF


def _type_matches(types_from_metadata, types_being_matched):
    for a_type in types_being_matched:
        if a_type not in types_from_metadata:
            return False
    return True


def _has_predicates(metadata, predicates):
    for predicate in predicates:
        if not metadata[predicate]:
            return False
    return True


class FedoraTypeManager:
    """
    A singleton responsible for creating instance of FedoraObject (and subclasses) out of RDFMetadata
    """

    models = set()

    # clazz -> (rdf_types, priority)
    on_rdf_types = {}

    # clazz -> (rdf_predicates, priority)
    on_rdf_predicates = {}

    @staticmethod
    def register_model(model_class, on_rdf_type=(), on_has_predicate=(), priority=1.0):
        """
        Register a model class

        :param model_class:         model class, must be inherited from FedoraObject
        :param on_rdf_type:         a tuple of rdf types which this class requires in the metadata
        :param on_has_predicate:    a tuple of predicates which this class required in the metadata
        :param priority:            priority which this class has in mro
        :return:
        """

        if model_class in FedoraTypeManager.models:
            return                              # already registered

        FedoraTypeManager.models.add(model_class)
        if on_rdf_type:
            FedoraTypeManager.on_rdf_types[model_class] = (on_rdf_type, priority)

        if on_has_predicate:
            FedoraTypeManager.on_rdf_predicates[model_class] = (on_has_predicate, priority)

    @staticmethod
    def get_model_class(classname):
        for model in FedoraTypeManager.models:
            if model.__name__ == classname:
                return model
        raise TypeError('Class with name %s is not registered as a model' % classname)

    @staticmethod
    def get_object_class(metadata, model_class=None):
        """
        Returns the best python class for the given metadata

        :param metadata:    the metadata
        :return:            python class which fits the metadata
        """

        from .models import FedoraObject

        types = metadata[RDF.type]

        possible_classes = {FedoraObject: 0}
        if model_class:
            possible_classes[model_class] = 1

        # look at classes registered on rdf types and if the class match, add it to the dict of possible classes
        for clz, rdf_and_priority in FedoraTypeManager.on_rdf_types.items():
            if _type_matches(types, rdf_and_priority[0]):
                possible_classes[clz] = max(possible_classes.get(clz, 0), rdf_and_priority[1])

        # look at classes registered on rdf predicates and if the class match, add it to the dict of possible classes
        for clz, rdf_and_priority in FedoraTypeManager.on_rdf_predicates.items():
            if _has_predicates(metadata, rdf_and_priority[0]):
                possible_classes[clz] = max(possible_classes.get(clz, 0), rdf_and_priority[1])

        # call class method handles_metadata and if it returns a priority, add the class as well
        for clz in FedoraTypeManager.models:
            priority = getattr(clz, 'handles_metadata')(metadata)
            if priority is not None and priority >= 0:
                possible_classes[clz] = max(possible_classes.get(clz, 0), priority)

        # convert to a list, add priorities from superclasses as well
        # (i.e. 2 * current_priority + sum of priorities of superclasses)
        propagated_possible_classes = []

        for clazz, priority in possible_classes.items():

            for clz in inspect.getmro(clazz):
                if clz in possible_classes:
                    priority += possible_classes[clz]

            propagated_possible_classes.append((clazz, priority))

        # sort by priority
        propagated_possible_classes.sort(key=lambda x: -x[1])

        # remove classes that are in mro of other classes
        classes = []
        seen_classes = set()
        for clazz, priority in propagated_possible_classes:
            if clazz in seen_classes:
                continue

            classes.append(clazz)

            for clz in inspect.getmro(clazz):
                seen_classes.add(clz)

        # got a list of classes, create a new type (or use a cached one ...)
        return FedoraTypeManager.generate_class(classes)

    @staticmethod
    def generate_class(classes):
        """
        generates a class which has the passed classes as superclasses

        :param classes: list of superclasses
        :return:    dynamically generated class
        """
        # TODO: class cache
        return type('_'.join([x.__name__ for x in classes]) + "_bound", tuple(classes), {'_is_bound':True})

    @staticmethod
    def populate():
        from django.apps import apps
        # loads all models.py files so that repository objects are configured ...
        apps.get_models()
