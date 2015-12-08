import logging

log = logging.getLogger('fedoralink.utils')


try:
    from cis_django_modules.cis_util.czech import czech_sorting_key
except:
    czech_sorting_key = lambda x:x


class StringLikeList(list):
    def __str__(self):
        if len(self) == 1:
            return str(self[0])
        return super(StringLikeList, self).__str__()


class TypedStream:
    def __init__(self, stream_or_filepath, mimetype=None, filename=None):
        """
        Creates a new instance of stream with optional mimetype and filename

        :param stream_or_filepath:  istream or optionally path on local filesystem
        :param mimetype:            mimetype. If not provided will be guessed
                                    (only if stream_or_filepath points to local file)
        :param filename:            filename in case stream_or_filepath is an input stream
        :return:
        """
        if isinstance(stream_or_filepath, str):
            self.__stream = None
            self.__filename = stream_or_filepath
            if mimetype is None:
                self.__mimetype = self.__guess_mimetype_from_filename(stream_or_filepath)
            else:
                self.__mimetype = mimetype
        else:
            self.__stream = stream_or_filepath
            self.__filename = filename
            if mimetype is None:
                self.__mimetype = 'application/binary'
            else:
                self.__mimetype = mimetype

    @property
    def stream(self):
        """
        Returns an input stream. Note that even though this method can be called more than once, the returned
        stream is always the same and might be already read up.

        :return:    istream
        """
        if not self.__stream and self.__filename is not None:
            self.__stream = open(self.__filename, 'rb')
        return self.__stream

    @property
    def mimetype(self):
        """
        Return mimetype or application/binary if mimetype can not be estimated
        """
        return self.__mimetype

    @property
    def filename(self):
        """
        Return the filename if it was set
        """
        return self.__filename

    @staticmethod
    def __guess_mimetype_from_filename(file_path):
        try:
            import magic
            return magic.from_file(file_path, mime=True)
        except Exception as e:
            log.error(e)
            return 'application/binary'


class OrderableModelList(list):

    def __init__(self, lst, model):
        super(OrderableModelList, self).__init__(lst)
        self._model = model

    def order_by(self, *args):
        lst = self[:]

        class NegatedKey(object):
            def __init__(self, obj, *args):
                self.obj = obj
            def __lt__(self, other):
                return self.obj > other
            def __gt__(self, other):
                return self.obj < other
            def __eq__(self, other):
                return self.obj == other
            def __le__(self, other):
                return self.obj >= other
            def __ge__(self, other):
                return self.obj <= other
            def __ne__(self, other):
                return self.obj != other

        def key(item):
            ret = []
            for arg in args:
                if '@' in arg:
                    arg, lang = arg.split('@')
                else:
                    lang = None

                if arg[0] in ('+', '-'):
                    asc, arg = arg[0], arg[1:]
                else:
                    asc = '+'

                arg = getattr(item, arg)

                item = None
                if lang is not None:
                    for a in arg:
                        if a.language == lang:
                            item = a.value
                            break
                if item is None:
                    if len(arg):
                        item = arg[0].value
                    else:
                        item = None

                item = item.strip()
                if lang == 'cs':
                    item = czech_sorting_key(item)

                if asc == '-':
                    ret.append(NegatedKey(item))
                else:
                    ret.append(item)
            return ret

        lst.sort(key=key)

        return OrderableModelList(lst, self._model)