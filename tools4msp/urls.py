from __future__ import absolute_import
from django.conf.urls import patterns, url, include
from .views import CaseStudyListView, CumulativeImpactInfo, CoexistInfo, \
    ESInfo, casestudy_configuration, casestudy_run_save, casestudy_run_view


urlpatterns = patterns('',
                       url(r'^casestudy/$',
                           CaseStudyListView.as_view(),
                           name='casestudy-list'),
                       url(r'coexistinfo',
                           CoexistInfo.as_view(),
                           name='coexistinfo'),
                       url(r'ciinfo',
                           CumulativeImpactInfo.as_view(),
                           name='ciinfo'),
                       url(r'esinfo',
                           ESInfo.as_view(),
                           name='esinfo'),
                       url(r'^casestudy/([0-9]+)/config$',
                           casestudy_configuration,
                           name='casestudy-conf'),
                       url(r'^casestudy/([0-9]+)/run$',
                           casestudy_run_save,
                           name='casestudy-run-save'),
                       url(r'^casestudy/([0-9]+)/([0-9]+)/view$',
                           casestudy_run_view,
                           name='casestudy-run-view'),
                   )
