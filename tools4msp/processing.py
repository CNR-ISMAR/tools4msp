

import logging
import re
from .georeaders import localgeonode
import geopandas as gpd

try:
    import rectifiedgrid as rg
except:
    pass
    
import numpy as np

logger = logging.getLogger('tools4msp.processing')

p = re.compile('{?((\w+)\:(\w+)(?:\[(.+?)\])?(?:\.(\w+))?)}?')


class Expression(object):
    def __init__(self, exp):
        self.exp = exp

    def parse(self):
        return p.sub(r"{}('\1')".format('self.get_resource'),
                     self.exp)

    def list(self):
        exp = self.exp
        if exp is None:
            return []
        return p.findall(self.exp)

    def eval(self, grid=None, res=None):
        logger.debug('Expression eval: {}'.format(self.exp))
        self.grid = grid
        self.res = res
        # TODO: improve parser
        return eval(self.parse())

    def get_resource(self, resource):
        return get_resource(resource, grid=self.grid, res=self.res)


def get_resource(resource, grid=None, res=None, **kwargs):
    _resource = resource.split('.')
    typename = _resource[0]
    column = None
    if len(_resource) == 2:
        column = _resource[1]

    geodataset = localgeonode(typename)

    if grid is not None:
        if isinstance(geodataset, gpd.GeoDataFrame):
            if 'eunismedscale' in typename:
                compute_area = True
            else:
                compute_area = False
            raster = rg.read_df_like(grid, geodataset, column=column, compute_area=compute_area)
        else:
            logger.debug('get_resource geodataset.dtype={}'.format(geodataset.dtype))
            raster = geodataset.astype(np.float).to_srs_like(grid.astype(np.float))
            # raster = domain_area_dataset.copy()
            # raster.reproject(geodataset)
    else:
        if isinstance(geodataset, gpd.GeoDataFrame):
            raster = rg.read_df(geodataset, res, column=column)
        else:
            # the res parameter is ignored
            raster = geodataset.copy().astype(np.float)

    return raster
