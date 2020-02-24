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
            print(s, e)
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


def partractest(request):
    # read grid raster
    r = PartracGrid.objects.all()[0]
    grid = r.rast.bands[0].data()
    grid[:] = 0

    rasters = []
    # get rasters
    cumraster = None
    for s, e in zip(TIMES, TIMES[1:]):
        if e == 216:
            e = 213
        start_time = s
        if s > 0:
            start_time = s + 1 # exclude endpoint
        params = {'GEO': INPUT_GEO_3035.buffer(BUFFER).to_wkt(),
                  'SCENARIO': SCENARIO,
                  'START_TIME': start_time,
                  # 'START_TIME': e, #start_time,
                  'END_TIME': e
        }
        df = pd.read_sql_query(QUERY, connection, params=params)
        df.dropna(inplace=True)
        df['count'] = df['count'].astype(int)
        df['grid_columnx'] = df['grid_columnx'].astype(int)
        df['grid_rowy'] = df['grid_rowy'].astype(int)
        #
        # ind = df[['grid_columnx', 'grid_rowy']].values
        raster = grid.copy()
        ind = (raster.shape[1] * df.grid_rowy + df.grid_columnx).values
        val = df['count'].values

        np.put(raster, ind,  val)

        gtransform = Affine.from_gdal(*r.rast.geotransform)
        proj = r.rast.srs.srid
        raster = rg.RectifiedGrid(raster, proj, gtransform)
        if cumraster is None:
            cumraster = raster
        else:
            cumraster += raster
            # cumraster = raster
        rasters.append([e, cumraster.copy()])
        print(start_time, e, cumraster.sum())

    fig, axs = plt.subplots(3, 3, figsize=(15, 20),
                            subplot_kw={'projection': CRS})
    axs = axs.ravel()

    cropped = rasters[-1][1].copy() # crop last cumraster
    cropped = cropped.crop(value=0)
    for i, (timeid, raster) in enumerate(rasters):
        ax = axs[i]
        raster = raster.to_srs_like(cropped)
        raster.mask = raster==0
        raster.plotmap(ax=ax, etopo=True, zoomlevel=6)
        ax.set_title('Time: {}'.format(timeid))
        ax.add_geometries([INPUT_GEO_3857.buffer(BUFFER)], crs=CRS,
                          facecolor="None",
                          edgecolor='black',
                          linewidth=4,
                          # alpha=0.4,
                          zorder=4)

    # fig.subplots_adjust(wspace=0, hspace=0)
    
    # plt.xlabel('time (s)')
    # plt.ylabel('voltage (mV)')

    print('Starting animation')
    # ani = animation.FuncAnimation(fig, run, init_func=init_run,
    #                               frames=10,
    #                               interval=500, blit=False)
    
    # Store image in a string buffer

    buffer = io.BytesIO()
    canvas = plt.get_current_fig_manager().canvas
    canvas.draw()
    pilImage = PIL.Image.frombytes("RGB", canvas.get_width_height(), canvas.tostring_rgb())
    pilImage.save(buffer, "PNG")
    plt.close()

    # Send buffer in a http response the the browser with the mime type image/png set
    return HttpResponse(buffer.getvalue(), content_type="image/png")


# 45.277475, 12.5335278
# 

# 
# r.rast.geotransform

# with r as (
#   select
#     geo,
#     grid_columnx,
#     grid_rowy,
#     reference_time_id
#   from tools4msp_partracdata
#   where scenario_id = 1 and particle_id = 85640 order by reference_time_id
# )
# select
# reference_time_id,
# next_time,
# round(ST_Distance(geo, next_geo) / 1000. ),
# grid_columnx,
# grid_rowy
# from
# (
# select
#   reference_time_id,
#   lead(reference_time_id) over (order by reference_time_id) as next_time,
#   geo,
#   lead(geo) over (order by reference_time_id) as next_geo,
#   grid_columnx,
#   grid_rowy
# from r
# order by reference_time_id
# ) as b;

                        
