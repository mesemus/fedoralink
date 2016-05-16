from django.conf.urls import url, include

import fedoralink_ui.views

urlpatterns = [url(r'^',
                   include(
                       [
                           url('choose-link/(?P<model_name>.*)', fedoralink_ui.views.link_choose, name='choose_link'),
                           url('detail/(?P<pk>.*)', fedoralink_ui.views.link_detail, name='detail'),
                       ],
                       namespace='fedoralink_ui', app_name='fedoralink_ui'))]
