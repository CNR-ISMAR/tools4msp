from django.urls import include, path
from .views import casestudy_run

# deprecated
# from django.conf.urls import patterns, url, include
# from .views import CaseStudyListView, CumulativeImpactInfo, CoexistInfo, \
#     ESInfo, CaseStudyRunConfigurationView, casestudy_run_save, CaseStudyRunView, \
#     HomeView


urlpatterns = [
    #
    path(r'^casestudy/(?P<object_pk>\d+)/run$',
         casestudy_run,
         name='casestudy-adminaction-run'),
    ]
# deprecated
                   #     url(r'^$',
                   #         HomeView.as_view(),
                   #         name='casestudy-admin-run'),
                   #     # this urls are deprecated
                   #     url(r'^$',
                   #         HomeView.as_view(),
                   #         name='tools4msp-home'),
                   #     url(r'^(?P<tool>[\w-]+)/$',
                   #         CaseStudyListView.as_view(),
                   #         name='casestudy-list'),
                   #     url(r'^(?P<tool>[\w-]+)/(?P<id>[0-9]+)/config$',
                   #         CaseStudyRunConfigurationView.as_view(),
                   #         name='casestudy-conf'),
                   #     url(r'^(?P<tool>[\w-]+)/(?P<id>[0-9]+)/run$',
                   #         casestudy_run_save,
                   #         name='casestudy-run-save'),
                   #     url(r'^(?P<tool>[\w-]+)/(?P<id>[0-9]+)/(?P<rid>[0-9]+)/view$',
                   #         CaseStudyRunView.as_view(),
                   #         name='casestudy-run-view'),
                   #     # info pages
                   #     url(r'coexistinfo',
                   #         CoexistInfo.as_view(),
                   #         name='coexistinfo'),
                   #     url(r'ciinfo',
                   #         CumulativeImpactInfo.as_view(),
                   #         name='ciinfo'),
                   #     url(r'esinfo',
                   #         ESInfo.as_view(),
                   #         name='esinfo'),
                   # )
