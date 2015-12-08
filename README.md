# fedoralink
Django access classes for Fedora Commons 4

Installation:

### 1. Create a new django project with a Python 3 virtual environment

```bash
cd /tmp
virtualenv testfedora-venv -p python3
. /tmp/testfedora-venv/bin/activate
pip install django
pip install git+https://github.com/mesemus/fedoralink.git
django-admin startproject testfedora
```

### 2. Add fedoralink into INSTALLED_APPS in settings.py:
```python
INSTALLED_APPS += [
    'fedoralink'
]
```
### 3. Add repository/ies into settings.py:
```python
DATABASES['repository'] = {
    'ENGINE'          : 'fedoralink.engine',
    'SEARCH_ENGINE'   : 'fedoralink.indexer.SOLRIndexer',
    'REPO_URL'        : 'http://127.0.0.1:8080/fcrepo/rest',
    'SEARCH_URL'      : 'http://127.0.0.1:8891/solr/collection1'
}
```

### 4. To test:

bash:
```bash
export DJANGO_SETTINGS_MODULE=testfedora.settings
python3
```

inside python:
```python
from fedoralink.models import FedoraObject

# empty pk is the root of the repository
list(FedoraObject.objects.filter(pk=''))

    INFO:fedoralink.connection:Requesting url http://127.0.0.1:8080/fcrepo/rest/
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): 127.0.0.1
    [<fedoralink.type_manager.FedoraObject_bound object at 0x7f36effcf6a0>]

```

### 5. Simple operations

#### Fetch a collection with a given pk (url)

```python
root = FedoraObject.objects.get(pk='')
```

#### Create a new subcollection

Pass a parameter "slug" to influence the URL of the created subcollection

```python
test = root.create_subcollection('test', slug='test')

# can set metadata here, not saved until .save() is called
test.save()
```

#### Set metadata

```python
from rdflib import Literal
from rdflib.namespace import DC

test[DC.title] = (
    Literal('Pokusný repozitář', lang='cs'),
    Literal('Test repository', lang='en'),
)

# changes are saved after this method is called
test.save()
```

#### Create a typed object

```python
from fedoralink.common_namespaces.dc import DCObject    
    
child = collection.create_child('name, will be copied to DC.title', flavour=DCObject)
child.title = 'Can use plain string as well as tuple with Literal.'
child.creator = 'ms'
child.save()
    
```

#### List children

```python

for child in collection.children:
    print("listing, child: ", child[DC.title])

```
