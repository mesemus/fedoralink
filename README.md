# fedoralink
Django access classes for Fedora Commons 4

Installation:

### 1. Create a new django project with a Python 3 virtual environment

```
cd /tmp
virtualenv testfedora-venv -p python3
. /tmp/testfedora-venv/bin/activate
pip install django
pip install 
django-admin startproject testfedora
```

### 2. Add fedoralink into INSTALLED_APPS in settings.py:
```
    INSTALLED_APPS += [
        'fedoralink'
    ]
```
### 3. Add repository/ies into settings.py:
```
    DATABASES['repository'] = {
        'ENGINE'          : 'fedoralink.engine',
        'SEARCH_ENGINE'   : 'fedoralink.indexer.SOLRIndexer',
        'REPO_URL'        : 'http://127.0.0.1:8080/fcrepo/rest',
        'SEARCH_URL'      : 'http://127.0.0.1:8891/solr/collection1'
    }
```

### 4. To test:

```
from fedoralink.models import FedoraObject

FedoraObject.objects.filter(pk='/')
```
