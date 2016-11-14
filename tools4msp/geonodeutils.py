"""Utility functions to msptools - geonode connection

TODO: they will be moved on models
TODO: a models.CaseStudy - casestudy.CaseStudy connection must be defined
"""

from __future__ import absolute_import

from .utils import raster_file_upload


def publish_grid(c, cs):
    """Publish the grid raster file and configure the CaseStudy

    Parameters
    ----------
    c : casestudy.CaseStudy
        Tools4map CaseStudy
    cs : models.CaseStudy
        django-based CaseStudy model
    """
    layer, style = raster_file_upload(c.datadir + 'grid.tiff',
                                      name='tools4msp-{}-grid'.format(c.name),
                                      title="Tools4MSP - CS {} - Grid".format(c.name))
    layer.is_published = True
    layer.save()
    cs.grid = layer
    cs.save()
