import logging
from django.db.transaction import get_connection
try:
    geonode = True
    from geonode.layers.models import Layer
except:
    geonode = False


import pandas as pd
import geopandas as gpd
import rectifiedgrid as rg

logger = logging.getLogger('tools4msp.georeaders')


def localgeonode(l):
    """Get a geo dataset from local GeoNonde installation. It returns a
       Rectifiedgrid object for raster layers and a GeoDataFrame for vector layers.
    """
    if not geonode:
        raise ModuleNotFoundError("GeoNode module is not installed or not configured in the project")
        return False
    if isinstance(l, int):
        l = Layer.objects.get(pk=l)
    elif isinstance(l, str):
        l = Layer.objects.get(typename=l)

    if l.is_vector():
        return get_df(l.name)
    else:
        path = l.upload_session.file_set.all()[0].file.path
        return rg.read_raster(path)


def get_df(lname):
    conn = get_connection('datastore')

    gc_df = pd.read_sql('select * from geometry_columns',
                        conn, index_col='f_table_name')
    srid = gc_df.loc[lname].srid
    gtype = gc_df.loc[lname].type
    gname = gc_df.loc[lname].f_geometry_column

    if gtype in ('POLYGON', 'MULTIPOLYGON'):
        sql = "select *, st_buffer({}, 0) as the_geom_clean from {} where {} is not null".format(gname, lname, gname)
    else:
        sql = "select *, {} as the_geom_clean from {} where {} is not null".format(gname, lname, gname)
    # print sql
    gdf = gpd.GeoDataFrame.from_postgis(sql,
                                        conn,
                                        geom_col='the_geom_clean',
                                        crs={'init': 'epsg:{}'.format(srid),
                                             'no_defs': True})
    # print lname, srid
    gdf.to_crs(epsg="3035", inplace=True)
    return gdf
