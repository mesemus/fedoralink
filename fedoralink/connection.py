from contextlib import closing
import io
import os.path
from urllib.parse import urljoin, urlparse, quote
from urllib.error import HTTPError
import time

import rdflib
from fedoralink.query import DoesNotExist
from fedoralink.utils import TypedStream

from .rdfmetadata import RDFMetadata
from .fedorans import FEDORA

import logging
import requests

log = logging.getLogger('fedoralink.connection')

# TODO: transactions

class RepositoryException(HTTPError):
    pass

class FedoraConnection:
    """
    A connection to fedora server
    """

    def __init__(self, fedora_url):
        """
        creates a new connection

        :param fedora_url: url of fedora REST api
        """
        self._fedora_url      = fedora_url
        if not self._fedora_url.endswith('/'):
            self._fedora_url +='/'

        self._in_transaction  = False
        self._transaction_url = ''

    def create_objects(self, data):
        """
        create new objects in Fedora repository

        :param data: list of resources to create, each:
                    {
                        metadata:  RDFMetadata (must contain FEDORA:hasParent property)
                        bitstream: optional bitstream to upload
                    }
        :return: list of modified metadata received from server.
                 Each is of type RDFMetadata and has 'id' property filled
        """
        metadata_from_server = []
        for item in data:
            metadata = item['metadata']
            parent_url = metadata[FEDORA.hasParent]
            if not parent_url:
                parent_url = ''
            else:
                parent_url = str(parent_url[0])
                del metadata[FEDORA.hasParent]
            parent_url = self._get_request_url(parent_url)

            if item['bitstream'] is not None:
                created_object_meta = self._create_object_from_bitstream(parent_url, item['bitstream'], item['slug'])
                self._update_single_resource(created_object_meta.id, metadata)
            else:
                created_object_meta = self._create_object_from_metadata(parent_url, metadata, item['slug'])

            metadata_from_server.append(created_object_meta)

        return metadata_from_server

    def _create_object_from_bitstream(self, parent_url, bitstream, slug):
        log.info('Creating child from bitstream in %s', parent_url)
        try:
            # TODO: this is because of Content-Length header, need to handle it more intelligently
            data = bitstream.stream.read()
            headers = {'Content-Type' : bitstream.mimetype}
            if bitstream.filename:
                filename_header = 'filename="%s"' % quote(os.path.basename(bitstream.filename).encode('utf-8'))
                headers['Content-Disposition'] = 'attachment; ' + filename_header
            if slug:
                headers['SLUG'] = slug
            resp = requests.post(parent_url, data, headers=headers)
            created_object_id = resp.text

            # do not make a version as this will be done after metadata are uploaded ...

            # need to get the metadata from the server as otherwise we would not be able to update the resource
            # later (Fedora mandates that last modification time in sent data is the same as last modification
            # time in the metadata on server)
            created_object_meta = list(self.get_object(created_object_id))[0]
            return created_object_meta

        except HTTPError as e:
            log.error("%s : %s", e.msg, e.fp.read())
            raise

    def _create_object_from_metadata(self, parent_url, metadata, slug):
        payload = str(metadata)
        log.info('Creating child in %s', parent_url)
        log.debug("    payload %s", payload)
        try:
            headers = {'Content-Type' : 'text/turtle; encoding=utf-8'}
            if slug:
                headers['SLUG'] = slug
            resp = requests.post(parent_url, payload.encode('utf-8'), headers=headers)
            created_object_id = resp.text

            # make a version
            self.make_version(created_object_id, time.time())

            # need to get the metadata from the server as otherwise we would not be able to update the resource
            # later (Fedora mandates that last modification time in sent data is the same as last modification
            # time in the metadata on server)
            created_object_meta = list(self.get_object(created_object_id))[0]
            return created_object_meta

        except HTTPError as e:
            log.error("%s : %s", e.msg, e.fp.read())
            raise

    def update_objects(self, data):
        """
        Update objects in repository

        :param data: Same as in create_objects, but must have 'id' property non-null
        :return:     list of modified metadata received from server.
                     Each is of type RDFMetadata and has 'id' property filled
        """
        metadata_from_server = []
        for item in data:
            metadata = item['metadata']
            url = self._get_request_url(metadata.id)
            metadata_from_server.append(self._update_single_resource(url, metadata))

        return metadata_from_server

    def _update_single_resource(self, url, metadata):
        payload = metadata.serialize_sparql()
        print(payload.decode('utf-8'))
        log.info("Updating object %s", url)
        log.debug("      payload %s", payload.decode('utf-8'))
        try:
            resp = requests.patch(url + "/fcr:metadata", data=payload,
                                  headers={'Content-Type': 'application/sparql-update; encoding=utf-8'})
            log.debug('Response: ', resp.content)
            if resp.status_code // 100 != 2:
                raise Exception('Error updating resource in Fedora: %s' % resp.content)
            self.make_version(metadata.id, time.time())

            # need to get the metadata from the server as otherwise we would not be able to update the resource
            # later (Fedora mandates that last modification time in sent data is the same as last modification
            # time in the metadata on server)
            created_object_meta = list(self.get_object(metadata.id))[0]
            return created_object_meta

        except HTTPError as e:
            log.error("%s : %s", e.msg, e.fp.read())
            raise


    def get_object(self, object_id, fetch_child_metadata=True):
        """
        Fetches the resource with the given object_id parameter

        :param object_id: id of the object. Might be full url or a fragment which will be appended after repository_url
        :return:    the RDFMetadata of the fetched object
        """
        try:
            req_url = self._get_request_url(object_id)
            log.info('Requesting url %s', req_url)
            headers = {
                'Accept' : 'application/rdf+xml; encoding=utf-8',
            }
            if fetch_child_metadata:
                headers['Prefer'] ='return=representation; ' + \
                                   'include="http://fedora.info/definitions/v4/repository#EmbedResources"'

            with closing(requests.get(req_url + "/fcr:metadata", headers=headers)) as r:

                g = rdflib.Graph()
                log.debug("making request to %s", req_url)
                log.debug(r.headers)
                log.debug(r.raw)
                data = r.content.decode('utf-8')
                if r.status_code//100 != 2:
                    raise RepositoryException(url=req_url, code=r.status_code,
                                              msg='Error accessing repository: %s' % data,
                                              hdrs=r.headers, fp=None)

            log.debug("   ... data %s", data)
            g.parse(io.StringIO(data))
            yield RDFMetadata(req_url, g)

        except HTTPError as e:
            log.error("%s: %s : %s", e.code, e.msg, e.fp.read() if e.fp else '')
            raise DoesNotExist(e)

    def raw_get(self, url):
        with closing(requests.get(url)) as r:
            if r.status_code // 100 != 2:
                raise HTTPError(url, r.status_code, r.content, hdrs=r.headers, fp=None)

            return r.content

    def get_bitstream(self, object_id):
        req_url = self._get_request_url(object_id)
        log.info("Bitstream request url %s", req_url)
        return requests.get(req_url, stream=True).raw

    def _remove_transactions_from_paths(self, data):
        # remove transaction from data ... let's do it the simple way even though it is not kosher
        if self._in_transaction:
            if not self._transaction_url.startswith(self._fedora_url):
                raise Exception('Error in getting transaction id: path %s not within fedora REST api %s' %
                                (self._transaction_url, self._fedora_url))

            txid = self._transaction_url[len(self._fedora_url):]
            if txid.startswith('/'):
                txid = txid[1:]
            if not txid.endswith('/'):
                txid += '/'

            # as txid is based on uuid, let's hope it occurs only in transactions ...
            data = data.replace(txid, '')
        return data

    def delete(self, object_id):
        """
        Deletes an object

        :param object_id:     id of the object. Might be full url or a fragment
                              which will be appended after repository_url
        """
        req_url = self._get_request_url(object_id)
        log.info('Deleting resource with url %s', req_url)
        req = requests.delete(req_url)

    def make_version(self, object_id, version):
        """
        Marks the current object data inside repository with a new version

        :param object_id:        id of the object. Might be full url or a fragment
                                 which will be appended after repository_url
        :param version:          the id of the version, [a-zA-Z_][a-zA-Z0-9_]*
        """
        requests.post(self._get_request_url(object_id) + '/fcr:versions',
                      headers={'Slug': 'snapshot_at_%s' % version})

    def begin_transaction(self):
        tx_prefix = "fcr:tx"
        url = self.dumb_concatenate_url(self._fedora_url, tx_prefix)
        log.info('Requesting transaction, url %s', url)
        req = requests.post(url)
        self._transaction_url = req.headers['Location']
        self._in_transaction = True

    @staticmethod
    def dumb_concatenate_url(url, tx_prefix):
        if url.endswith('/'):
            url += tx_prefix
        else:
            url += "/" + tx_prefix
        return url

    def commit(self):
        self._end_transaction(True)

    def _end_transaction(self, do_commit):
        try:
            if self._in_transaction:
                url = self.dumb_concatenate_url(self._transaction_url,
                                                'fcr:tx/' + ('fcr:commit' if do_commit else 'fcr:rollback'))
                log.info('Finishing transaction, url %s', url)
                req = requests.post(url)
        finally:
            self._in_transaction = False
            self._transaction_url = ''

    def _get_request_url(self, object_id):
        if ':' in object_id and not object_id.startswith('http'):
            req_url = self._fedora_url + '/' + object_id
        else:
            req_url = urljoin(self._fedora_url, object_id)
        if self._in_transaction:
            if not req_url.startswith(self._fedora_url):
                raise Exception('Could not relativize request url so that it can play part in transaction. ' +
                                'Object url %s, fedora url %s' % (req_url, self._fedora_url))
            req_url = req_url[len(self._fedora_url):]
            if req_url.startswith('/'):
                req_url = req_url[1:]
            if req_url.startswith('tx:'):
                slashpos = req_url.find('/')
                txid = req_url[:slashpos]
                req_url = req_url[slashpos+1:]
                # TODO: check txid
            req_url = self.dumb_concatenate_url(self._transaction_url, req_url)
        return req_url

    def rollback(self):
        self._end_transaction(False)

    def direct_put(self, url, data, content_type='application/binary'):
        if isinstance(data, str):
            data = data.encode('utf-8')
        try:
            req = requests.put(self._get_request_url(url), data=data, headers={'Content-Type': content_type})
            log.debug(req.text)
        except HTTPError as e:
            log.error("Error when calling directput at {0}: {1}".format(url, e.fp.read()))

    def __eq__(self, other):
        if not hasattr(other, '_fedora_url'):
            return False
        return self._fedora_url == other._fedora_url
