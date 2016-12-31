Django authorization plugin for fcrepo
======================================

Purpose
-------

Each authenticated user in django is given a set of groups. 
When fedoralink calls django, it uses the identity 
(username/password) configured in `DATABASES` section
of `settings.py`,  not the username/password of the current user.

To pass the current user to fcrepo, fedoralink adds two 
headers to http communication:

1. Standard `On-Behalf-Of` header. The header is interpreted 
   by DelegateHeaderPrincipalProvider that is by default 
   included in fcrepo w/ webac.
   The value of the header is in the following form:
    * if username looks like an email (for example `simeki@vscht.cz`):
        
            urn:vscht.cz/simeki
        
    * otherwise:
    
            urn:admin
         
2. Groups are passed in a `On-Behalf-Of-Django-Groups` header
   separated with `,`. The format of each group name is 
   `urn:django:<groupname>`. For example, group with name 
   `vscht` is serialized into `urn:django:vscht`.
   
   This header is interpreted by `DjangoGroupPrincipalProvider`
   class included in this package.
   
Installation
------------

1. Check out fedoralink, go to fedora_group_plugin directory and
   run 
    > mvn install

2. Copy `target/cesnet-fcrepo-auth-django-<version>.jar` into `fcrepo.war`,
   directory `WEB-INF/lib/`
   
3. Modify `WEB-INF/classes/spring/auth-repo.xml`, and add/change the following:

        <bean name="djangoGroupPrincipalProvider" 
              class="cz.cesnet.fcrepo.auth.django.DjangoGroupPrincipalProvider"/>

        <util:set id="principalProviderSet">
          <ref bean="djangoGroupPrincipalProvider"/>
          <ref bean="delegatedPrincipalProvider"/>
        </util:set>
