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
from tools4msp.models import PartracGrid
from django.db import connection
import pandas as pd
from affine import Affine
from shapely.geometry import MultiPoint
import cartopy
from shapely.ops import transform
from functools import partial
import pyproj
import matplotlib.animation as animation
from .casestudy import CaseStudyBase




QUERY = """
with 
  starting_particles as (select particle_id from tools4msp_partracdata 
        where scenario_id = %(SCENARIO)s and reference_time_id=0 and st_contains(st_setsrid(ST_GeomFromText(%(GEO)s), 3035), geo)) 
  select count(*), grid_columnx, grid_rowy  from tools4msp_partracdata where scenario_id=%(SCENARIO)s and particle_id in (select * from starting_particles) 
  and reference_time_id between %(START_TIME)s and %(END_TIME)s
group by grid_columnx, grid_rowy;
"""

INPUT_GEO = MultiPoint([
    (12.923794, 44.015206),
    (13.812849, 44.838672),
    (12.419255, 45.426838),
    (12.337239, 45.335001),
    (12.553829, 44.940228),
    (13.734475, 45.641482),
])

CRS = cartopy.crs.Mercator()

to3857 = partial(
    pyproj.transform,
    pyproj.Proj(init='epsg:4326'),
    pyproj.Proj(CRS.proj4_init)
)

to3035 = partial(
    pyproj.transform,
    pyproj.Proj(init='epsg:4326'),
    pyproj.Proj(init='epsg:3035')
)

INPUT_GEO_3857 = transform(to3857, INPUT_GEO)
INPUT_GEO_3035 = transform(to3035, INPUT_GEO)

BUFFER = 5000
SCENARIO = 1

# questo arriva a 216 anche se il limite vero e' 213
TIMES = list(range(0, 217, 24)) 


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

                        
