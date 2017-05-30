from __future__ import absolute_import

from django.contrib.gis.db import models
from geonode.layers.models import Layer
from msptools.cumulative_impact.models import CICaseStudy
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField

LAYER_TYPE_CHOICES = (
    ('use', 'Activity & Uses'),
    ('env', 'Environmental Component'),
    ('pre', 'Pressure'),
)


class CaseStudyRun(models.Model):
    casestudy = models.ForeignKey(CICaseStudy)
    name = models.CharField(max_length=100, blank=True, null=True)
    out_ci = models.ForeignKey(Layer, blank=True, null=True, related_name='casestudyrun_ci')
    out_coexist = models.ForeignKey(Layer, blank=True, null=True, related_name='casestudyrun_coexist')
    area_of_interest = models.MultiPolygonField(blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, related_name='owned_casestudyrun',
                              verbose_name=_("Owner"))
    # temporary storage for uses a
    configuration = JSONField()


# class CaseStudyRunLayers(models.Model):
#     lid = models.CharField(max_length=5)
#     label = models.CharField(max_length=5)
#     ltype = models.CharField(max_length=5, choices=LAYER_TYPE_CHOICES)
