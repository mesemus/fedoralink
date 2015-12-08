__author__ = 'simeki'

import requests
from lxml import etree
import io

if False:
    dataxml = requests.get('http://localhost:8080/fcrepo/rest/fcr:export?format=jcr/xml&recurse=true').raw
else:
    dataxml = open('/data/tmp/test1.xml', 'r')

root = etree.parse(dataxml)

def piter(node, parentpath=()):
    ppth = parentpath
    ppth = ppth + (node,)
    yield ppth
    for c in list(node):
        for r in piter(c, ppth):
            yield r

def get_url(path):
    return '/'.join([
        x.attrib['{http://www.jcp.org/jcr/sv/1.0}name'] for x in path
    ])


for path in piter(root.getroot()):

    if path[-1].tag == '{http://www.jcp.org/jcr/sv/1.0}node':
        found = False
        for val in path[-1].xpath('./sv:property/sv:value', namespaces={'sv':'http://www.jcp.org/jcr/sv/1.0'}):
            if val.text == 'fedora:Tombstone':
                found = True
                break
        if found:
            print(get_url(path))

