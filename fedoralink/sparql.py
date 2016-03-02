from rdflib import Literal

__author__ = 'simeki'

from rdflib.plugins.serializers.turtle import TurtleSerializer, VERB, OBJECT


class SparqlSerializer(TurtleSerializer):

    def __init__(self, base, deleted_triplets, inserted_triplets):
        super().__init__(base)
        self.deleted_triplets = deleted_triplets
        self.inserted_triplets = inserted_triplets

    def serialize(self, stream, base=None, encoding=None, spacious=None, **args):
        self.reset()
        self.stream = stream
        self.base = base

        if spacious is not None:
            self._spacious = spacious

        # self.preprocess()
        # subjects_list = self.orderSubjects()

        self.startDocument()

        self.write('DELETE {\n')

        for predicate, objects in self.deleted_triplets.items():
            for object in objects:
                self.write('    <> ')
                self.path(predicate, VERB)
                self.path(object, OBJECT)
                self.write(' .\n')

        self.write('}\n')

        self.write('INSERT {\n')

        for predicate, objects in self.inserted_triplets.items():
            for object in objects:
                self.write('    <> ')
                self.path(predicate, VERB)
                self.path(object, OBJECT)
                self.write(' .\n')


        self.write('}\n')

        self.write('WHERE { }\n')

        self.endDocument()
        stream.write("\n".encode('ascii'))

    def startDocument(self):
        self._started = True
        ns_list = sorted(self.namespaces.items())
        for prefix, uri in ns_list:
            self.write(self.indent() + 'PREFIX %s: <%s>\n' % (prefix, uri))
        if ns_list and self._spacious:
            self.write('\n')


    def label(self, node, position):
        if isinstance(node, Literal):
            if node.datatype:
                node = Literal(node.value, lang=node.language)
            return node._literal_n3(
                use_plain=True,
                qname_callback=lambda dt: None)
        return super().label(node, position)
