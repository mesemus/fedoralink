# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class ApplicationConfig(AppConfig):
    name = 'fedoralink_ui'
    verbose_name = _("User interface module for fedoralink")

    def ready(self):
        super().ready()

        from django.conf import settings
        for tmpl in settings.TEMPLATES:
            options = tmpl.setdefault('OPTIONS', {'context_processors': []})
            context_processors = options.setdefault('context_processors', [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ])
            context_processors.append('fedoralink_ui.views.appname')