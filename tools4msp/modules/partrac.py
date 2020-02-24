# file charts.py
import rectifiedgrid as rg
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from matplotlib import pyplot as plt
import io
import random
import django
import datetime
import PIL, PIL.Image
import io
import numpy as np
from django.http import HttpResponseRedirect, HttpResponse
from django.db.models import Max
from django.db import connection
import pandas as pd
import geopandas as gpd
from affine import Affine
from shapely.geometry import MultiPoint
import cartopy
from shapely.ops import transform
from functools import partial
import pyproj
import matplotlib.animation as animation
from .casestudy import CaseStudyBase
from os import path


QUERY = """
with 
  starting_particles as (
    select particle_id
    from tools4msp_partracdata 
    where scenario_id = %(SCENARIO)s 
          and reference_time_id=0
          and st_contains(st_setsrid(ST_GeomFromText(%(GEO)s), 3035), geo)
  ) 
  select count(*), 
         grid_columnx, grid_rowy
  from tools4msp_partracdata 
  where scenario_id=%(SCENARIO)s
        and particle_id in (select * from starting_particles) 
        and reference_time_id > %(START_TIME)s 
        and reference_time_id <= %(END_TIME)s
  group by grid_columnx, grid_rowy;
"""


def parse_sources(sources):
    gdf = gpd.GeoDataFrame.from_features(sources, crs={'init': 'epsg:4326'})
    gdf.to_crs(epsg=3035, inplace=True)
    return gdf


class ParTracCaseStudy(CaseStudyBase):
    def __init__(self,
                 csdir=None,
                 rundir=None,
                 name='unnamed'):

        super().__init__(csdir=csdir,
                         rundir=rundir,
                         name='unnamed')

    def load_grid(self):
        from tools4msp.models import PartracGrid

        r = PartracGrid.objects.all()[0]
        grid = r.rast.bands[0].data()
        grid[:] = 0
        gtransform = Affine.from_gdal(*r.rast.geotransform)
        proj = r.rast.srs.srid
        self.grid = rg.RectifiedGrid(grid, proj, gtransform)

    def load_inputs(self):
        spath = path.join(self.inputsdir, 'partrac-PARTRACSOURCES.geojson')
        if path.isfile(spath):
            _df = gpd.read_file(spath)
            self.sources = _df

        super().load_inputs()

    def run(self, scenario, sources=None):
        from tools4msp.models import PartracGrid, PartracData
        if sources is not None:
            gdf = parse_sources(sources)
        else:
            gdf = self.sources
            gdf.to_crs(epsg=3035, inplace=True)

        buffer = 1000

        # set time intervals
        max_time = PartracData.objects.filter(scenario=scenario).aggregate(Max('reference_time_id'))['reference_time_id__max']
        step = 24
        times = list(range(-step, max_time + 1, step))
        time_intervals = zip(times, times[1:])

        self.outputs['time_rasters'] = []
        # get rasters
        cumraster = None
        for s, e in time_intervals:
            params = {'GEO': gdf.buffer(buffer).unary_union.to_wkt(),
                      'SCENARIO': scenario,
                      'START_TIME': s,
                      'END_TIME': e
                      }
            df = pd.read_sql_query(QUERY,
                                   connection,
                                   params=params)
            df.dropna(inplace=True)
            df['count'] = df['count'].astype(int)
            df['grid_columnx'] = df['grid_columnx'].astype(int)
            df['grid_rowy'] = df['grid_rowy'].astype(int)
            #
            # ind = df[['grid_columnx', 'grid_rowy']].values
            raster = self.grid.copy()
            ind = (raster.shape[1] * df.grid_rowy + df.grid_columnx).values
            val = df['count'].values

            np.put(raster, ind, val)

            # gtransform = Affine.from_gdal(*r.rast.geotransform)
            # proj = r.rast.srs.srid
            # raster = rg.RectifiedGrid(raster, proj, gtransform)
            if cumraster is None:
                cumraster = raster.copy()
            else:
                cumraster += raster
            self.outputs['time_rasters'].append([e, cumraster.copy(), raster.copy()])
        return True


