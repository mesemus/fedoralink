import requests

from fedoralink.middleware import FedoraUserDelegationMiddleware

HTTPError = requests.HTTPError

def wrapper(func):
    def wrapped(*args, **kwargs):
        kwargs = dict(kwargs)
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if FedoraUserDelegationMiddleware.is_enabled():
            kwargs['headers']['On-Behalf-Of'] = ','.join(FedoraUserDelegationMiddleware.get_on_behalf_of())
        return func(*args, **kwargs)
    return wrapped


post = wrapper(requests.post)
put = wrapper(requests.put)
get = wrapper(requests.get)
patch = wrapper(requests.patch)
delete = wrapper(requests.delete)
