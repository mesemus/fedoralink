
class IndexedField:
    def __init__(self, rdf_name, required=False, verbose_name=None, attrs=None):
        self.rdf_name     = rdf_name
        self.required     = required
        self.verbose_name = verbose_name
        self.attrs        = attrs if attrs else {}


class IndexedMultiLangField(IndexedField):
    pass


class IndexedTextField(IndexedField):
    pass


class IndexedDateField(IndexedField):
    pass