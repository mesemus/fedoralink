import traceback

import logging
import requests

from fedoralink.middleware import FedoraUserDelegationMiddleware, FedoraProfillingMiddleware

HTTPError = requests.HTTPError


def wrapper(func):
    import time
    def wrapped(*args, **kwargs):
        kwargs = dict(kwargs)
        do_debug = FedoraProfillingMiddleware.profilling_enabled()
        if do_debug:
            t1 = time.time()
        try:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            if FedoraUserDelegationMiddleware.is_enabled():
                kwargs['headers']['On-Behalf-Of'] = ','.join(FedoraUserDelegationMiddleware.get_on_behalf_of())
                kwargs['headers']['On-Behalf-Of-Django-Groups'] = \
                    ','.join(FedoraUserDelegationMiddleware.get_on_behalf_of_groups())
            return func(*args, **kwargs)
        finally:
            if do_debug:
                t2 = time.time()
                # noinspection PyUnboundLocalVariable
                FedoraProfillingMiddleware.log_time(args[0] + ' - ' + repr(args[1:]) + repr(kwargs), t2-t1)
    return wrapped


post = wrapper(requests.post)
put = wrapper(requests.put)
get = wrapper(requests.get)
patch = wrapper(requests.patch)
delete = wrapper(requests.delete)
