# coding: utf-8

from __future__ import absolute_import

import re
import simplejson
import itertools
import numpy as np
import operator
import scipy
import pandas as pd
import rectifiedgrid as rg
from rasterio.warp import reproject, RESAMPLING

from geonode.base.models import DataAvailabilityArea
from msptools.conflict_score.models import ActivityAndUse
from msptools.cumulative_impact.models import CICaseStudy, Sensitivity, EnvironmentalComponent, Pressure
from geonode.layers.models import Layer
from msptools.base.utils import get_model
from shapely.geometry import shape
from geopandas import GeoDataFrame
from django.db.transaction import get_connection
from mamat import CumulativeImpact
import matplotlib.pyplot as plt
from geonode.layers.utils import file_upload
from geonode.geoserver.helpers import gs_catalog

from djsld import generator

from .casestudy import CaseStudy


def get_casestudy(ci_id, cellsize, basedir,
                  version='v1', rtype='full',
                  casestudy=None, cache=True):
    if casestudy is None:
        # geo = get_aim(3035)
        geo = get_cs_area(ci_id, 3035)

        grid = rg.read_features([geo], cellsize, 3035, eea=True)

        # set the mask
        grid[grid == 0] = np.ma.masked

        casestudy = CaseStudy(grid, basedir=basedir, name=str(ci_id),
                              version=version, rtype=rtype)

    cics, uses, envs = _get_adriplan_cics(ci_id)

    # USES
    for use, use_layers in list(uses.iteritems()):
        # print "USE", use
        update_use(casestudy, ci_id, use, cache=cache)
        # print casestudy.layers.loc['u{}'.format(use.id), 'availability']

    # ENVS
    for env, env_layers in list(envs.iteritems()):
        # print "ENVS", env
        # if env.label == 'A5.39 - Mediterranean biocenosis of coastal terrigenous muds':
        update_env(casestudy, ci_id, env, cache=cache)

    return casestudy


def update_coexist_scores(casestudy, ci_id):
    cics, uses, envs = _get_adriplan_cics(ci_id)

    combs = list(itertools.combinations(uses, 2))
    for use1, use2 in combs:
        if use1 != use2:
            use1id = 'u{}'.format(use1.id)
            use2id = 'u{}'.format(use2.id)
            use1label = use1.label
            use2label = use2.label
            vscale1 = use1.vertical_scale.value
            vscale2 = use2.vertical_scale.value
            mobility1 = use1.mobility.value
            mobility2 = use2.mobility.value
            spatial1 = use1.spatial_scale.value
            spatial2 = use2.spatial_scale.value
            time1 = use1.time_scale.value
            time2 = use2.time_scale.value

            casestudy.add_coexist_score(use1id, use1label,
                                        use2id, use2label,
                                        [vscale1, spatial1, time1, mobility1],
                                        [vscale2, spatial2, time2, mobility2])


def get_use_obj(use):
    if isinstance(use, ActivityAndUse):
        return use
    elif isinstance(use, int):
        return ActivityAndUse.objects.get(pk=use)
    elif isinstance(use, str) or isinstance(use, unicode):
        return ActivityAndUse.objects.get(label=use)


def get_env_obj(env):
    if isinstance(env, EnvironmentalComponent):
        return env
    elif isinstance(env, int):
        return EnvironmentalComponent.objects.get(pk=env)
    elif isinstance(env, str) or isinstance(env, unicode):
        return EnvironmentalComponent.objects.get(label=env)


def get_use_layers(ci_id, use):
    cics, uses, envs = _get_adriplan_cics(ci_id)
    o = get_use_obj(use)
    return uses[o]


def get_env_layers(ci_id, env):
    cics, uses, envs = _get_adriplan_cics(ci_id)
    o = get_env_obj(env)
    return envs[o]


def _get_adriplan_cics(ci_id):
    cics = CICaseStudy.objects.get(pk=ci_id)
    uses = cics._group_uses()
    envs = cics._group_envs()
    return cics, uses, envs


def get_use_raster(ci_id, use, grid):
    use = get_use_obj(use)
    use_layers = get_use_layers(ci_id, use)

    raster = None
    if ci_id == 15 and use.label == 'Maritime Transport':
        raster = get_traffic(grid)
        raster.mask = grid.mask
        return raster
    elif ci_id == 15 and use.id == 85:
        raster = get_trawling3(grid)
        raster.mask = grid.mask
        return raster
    elif ci_id == 15 and use.id == 87:
        raster = get_small_scale_fishery(grid)
        raster.mask = grid.mask
        return raster
    elif (ci_id == 15 or ci_id == 16) and use.label == 'Military Areas':
        raster = layers_to_raster(use_layers, grid, compute_area=False)
        raster[~scipy.ndimage.binary_erosion(raster)] = 0
        raster.gaussian_filter(2000 / grid.resolution, truncate=3.0)
        raster = raster / 3. # come in andersen
        return raster
    elif (ci_id == 18) and use.label == 'Military Areas':
        print "Process military areas 2"
        raster = layers_to_raster(use_layers, grid, compute_area=False)
        # raster[~scipy.ndimage.binary_erosion(raster)] = 0
        # raster.gaussian_filter(2000 / grid.resolution, truncate=3.0)
        raster = raster / 3. # come in andersen
        return raster
    elif ci_id == 15 and use.label == 'Oil & Gas research':
        raster = layers_to_raster(use_layers, grid, compute_area=False)
        raster[~scipy.ndimage.binary_erosion(raster)] = 0
        raster.gaussian_filter(2000 / grid.resolution, truncate=3.0)
        raster = raster / 3. # come in andersen
        return raster
    elif ci_id == 15 and use.label == 'Oil & Gas extraction':
        raster = get_oil_and_gas_extraction(grid)
        raster.mask = grid.mask
        return raster
    elif (ci_id == 15 or ci_id == 18) and use.id == 76:
        raster = get_coastal_and_maritime_tourism(grid)
        raster.mask = grid.mask
        return raster
    elif (ci_id == 15 or ci_id == 18) and use.label == 'Naval base activities':
        raster = get_naval_base_activities(grid)
        raster.mask = grid.mask
        return raster
    # Case Study RER - Cumulative Impact
    elif ci_id == 18 and use.label == 'Maritime Transport':
        raster = get_traffic_orig(grid, 3)
        raster.mask = grid.mask
        return raster
    elif ci_id == 18 and use.id == 87:
        raster = get_small_scale_fishery_01_12(grid)
        raster.mask = grid.mask
        military_layers = get_use_layers(ci_id, 88)
        military = layers_to_raster(military_layers, grid, compute_area=False)
        raster[military>0] = 0
        return raster
    elif ci_id == 18 and use.label == 'Flying':
        raster = get_flying(grid)
        raster.mask = grid.mask
        return raster
    elif ci_id == 18 and use.id == 85:
        raster = get_trawling_gsa(grid)
        raster.mask = grid.mask
        return raster
    # Case Study RER COEXIST + Italian Adriatic COEXIST
    elif ci_id in (16, 21) and use.label == 'Maritime Transport':
        raster = get_traffic_orig(grid, 3)
        raster.mask = grid.mask
        return raster
    elif ci_id in (16, 21) and use.id == 85:
        raster = get_trawling_gsa(grid, 30)
        raster.mask = grid.mask
        return raster
    elif ci_id in (16, 21) and use.label == 'Flying':
        raster = get_flying(grid, 10)
        raster.mask = grid.mask
        return raster
    else:
        return layers_to_raster(use_layers, grid, compute_area=False)


def get_env_raster(ci_id, env, grid):
    env = get_env_obj(env)
    env_layers = get_env_layers(ci_id, env)

    if env.id == 26:
        print "Nursery"
        raster = get_nursery_habitats(grid)
        raster.mask = grid.mask
        return raster
    if env.label == 'TU - Turtles':
        print "Turtles"
        raster = get_turtles(grid)
        raster.mask = grid.mask
        return raster
    elif env.label == 'GDR - Giant devil ray':
        print "Ray"
        raster = get_ray(grid)
        raster.mask = grid.mask
        return raster
    elif env.label == 'MM - Marine mammals':
        print "Mammals"
        raster = get_marine_mammals(grid)
        raster.mask = grid.mask
        return raster
    elif env.label == 'SB - Seabirds':
        print "Seabirds"
        return get_marine_seabirds(grid)
    elif env.label == 'A4.26 - Mediterranean coralligenous communities':
        print "Coralligenous"
        return get_coralligenous(grid)
    elif env.label == 'A5.535 - Posidonia beds':
        print "Posidonia"
        return get_posidonia_beds(grid)
    elif re.match(r'A\d\d?', env.label):
        print "AREA", env.label
        return layers_to_raster(env_layers, grid, compute_area=True) # rimettere a True quando sarà finito
    elif re.match(r'EM', env.label):
        print "AREA", env.label
        return layers_to_raster(env_layers, grid, compute_area=True) # rimettere a True quando sarà finito
    else:
        print "OTHER", env.label
        return layers_to_raster(env_layers, grid, compute_area=False)


def update_use(casestudy, ci_id, use, cache=True):
    use = get_use_obj(use)
    grid = casestudy.grid
    use_layers = get_use_layers(ci_id, use)

    lid = 'u{}'.format(use.id)
    if cache:
        raster = casestudy.read_raster(lid)
    else:
        print use
        raster = get_use_raster(ci_id, use, grid)
    if cache:
        raster_availability = casestudy.read_raster('av_' + lid)
    else:
        raster_availability = availability_to_raster(use_layers, grid)
    # print raster_availability
    casestudy.add_layer(raster, 'use', lid=lid,
                        label=use.label,
                        availability=raster_availability)


def update_env(casestudy, ci_id, env, cache=True):
    env = get_env_obj(env)
    grid = casestudy.grid
    env_layers = get_env_layers(ci_id, env)

    lid = 'e{}'.format(env.id)
    if cache:
        raster = casestudy.read_raster(lid)
    else:
        print env
        raster = get_env_raster(ci_id, env, grid)
    if cache:
        raster_availability = casestudy.read_raster('av_' + lid)
    else:
        raster_availability = availability_to_raster(env_layers, grid)
    # print raster_availability
    casestudy.add_layer(raster, 'env', lid=lid,
                        label=env.label,
                        availability=raster_availability)


def get_adriplan_cics(ci_id, cellsize, datadir=None, casestudy=None, cache=True):
    if casestudy is None:
        # geo = get_aim(3035)
        geo = get_cs_area(ci_id, 3035)

        grid = rg.read_features([geo], cellsize, 3035, eea=True)

        # set the mask
        grid[grid == 0] = np.ma.masked

        casestudy = CumulativeImpact(grid, datadir=datadir)

    cics, uses, envs = _get_adriplan_cics(ci_id)

    # USES
    for use, use_layers in list(uses.iteritems()):
        # print "USE", use
        update_use(casestudy, ci_id, use, cache=cache)
        # print casestudy.layers.loc['u{}'.format(use.id), 'availability']

    # ENVS
    for env, env_layers in list(envs.iteritems()):
        # print "ENVS", env
        # if env.label == 'A5.39 - Mediterranean biocenosis of coastal terrigenous muds':
        update_env(casestudy, ci_id, env, cache=cache)

    return casestudy


def update_sensitivities(casestudy, ci_id):
    cics, uses, envs = _get_adriplan_cics(ci_id)

    combs = list(itertools.product(uses, envs))

    casestudy.sensitivities = casestudy.sensitivities[0:0]  # empty

    for p in combs:
        use = p[0]
        env = p[1]

        sens = get_sensitivities_by_rule(use, env)

        for s in sens:
            distance = s.distance
            casestudy.add_sensitivity(
                'u{}'.format(use.id),
                use.label,
                'e{}'.format(env.id),
                env.label,
                'p{}'.format(s.pressure.id),
                s.pressure.label,
                s.total_score, distance, s.confidence
            )


##################################
def get_nursery_habitats(grid):
    l1 = Layer.objects.get(name='nursery_s_na')
    l2 = Layer.objects.get(name='nursery_r_na')

    r1 = layers_to_raster([l1], grid, 'na_s_na')
    r1.norm()

    r2 = layers_to_raster([l2], grid, 'nur_tot_na')
    r2.norm()

    r12 = r1 + r2
    r12.norm()
    return r12


def get_naval_base_activities(grid):
    l1 = Layer.objects.get(name='cargo_ports_2014')

    buffer = 10000
    r1 = layers_to_raster([l1], grid, 'ports_CLAS')
    r1.gaussian_filter(buffer / grid.resolution, truncate=3.0)
    r1.norm()
    return r1


def get_oil_and_gas_extraction(grid):
    l1 = Layer.objects.get(name='hydrocarbon_extraction_platform')
    # l2 = Layer.objects.get(name='hydrocarbonexploitation_it_active_20150430')
    # l3 = Layer.objects.get(name='developmentareas_croatia')

    r1 = layers_to_raster([l1], grid)
    # r2 = layers_to_raster([l2], grid)
    # r3 = layers_to_raster([l3], grid)

    # r123 = r1 + r2*0.2 + r3*0.2
    # r123.norm()
    # return r123

    r1.norm()
    return r1


def get_coastal_and_maritime_tourism(grid):
    l1 = Layer.objects.get(name='marinas_fa2_gr')
    l2 = Layer.objects.get(name='marina')

    # si suppone un media di 200 barche
    buffer = 20000
    r1 = layers_to_raster([l1], grid, 'ORIG_FID', value=200)
    r1.gaussian_filter(buffer / grid.resolution / 2., truncate=3.0)

    r2 = layers_to_raster([l2], grid, 'barche', value=200)

    r2.gaussian_filter(buffer / grid.resolution / 2., truncate=3.0)

    r12 = r1 + r2
    r12.lognorm()
    return r12


def get_ray(grid):
    l = Layer.objects.get(name='giantdevilray_count')
    raster = layers_to_raster([l], grid, 'count')
    raster.norm()
    raster.gaussian_filter(2500 / grid.resolution, truncate=3.0)
    return raster


def get_turtles(grid):
    l = Layer.objects.get(name='loggerheadturtles_gridcount')
    raster = layers_to_raster([l], grid, 'turtle_c')
    raster.norm()
    raster.gaussian_filter(2500 / grid.resolution, truncate=3.0)
    return raster


def get_marine_mammals(grid):
    l = Layer.objects.get(name='marinemammals_gridcount_1')
    raster = layers_to_raster([l], grid, 'count')
    raster.norm()
    raster.gaussian_filter(2500 / grid.resolution, truncate=3.0)
    return raster


def get_marine_seabirds(grid):
    l = Layer.objects.get(name='seabirds_distribution_grid_adriatic')
    r1 = layers_to_raster([l], grid, 'CONSVAL_S')
    r1.norm()

    l = Layer.objects.get(name='marine_birds_ionian2')
    r2 = layers_to_raster([l], grid, 'CONSVAL_S')
    r2.norm()

    # uso i 5/7 come da
    # Report presenting a georeferenced
    # compilation on bird important areas in the
    # Mediterranean open seas
    return (r1 + r2) * 5. / 7.


def get_coralligenous(grid):
    l = Layer.objects.get(name='cormed50_0')
    raster = layers_to_raster([l], grid, 'GRID_CODE')
    raster.norm()
    return raster


def get_posidonia_beds(grid):
    l = Layer.objects.get(name='posshp_0')
    raster = layers_to_raster([l], grid, 'GRID_CODE')
    # 1 = Present
    # 2 = Possibly present
    # 3 Most probably absent
    # 4 Absent
    #
    # raster[raster == 0] = 4
    raster[raster == 2] = 0.5
    raster[raster == 3] = 0
    raster[raster == 4] = 0
    raster.norm()
    return raster


def get_traffic_orig(grid, truncate=None):
    _r = rg.read_raster('/var/www/geonode/uploaded/layers/traffic_density_2014.tif')
    raster = grid.copy()
    raster.reproject(_r)
    raster.positive()
    if truncate is not None:
        raster[raster < truncate] = 0
    raster.lognorm()
    return raster


def get_traffic(grid, truncate=None):
    _r = rg.read_raster('/var/www/geonode/uploaded/layers/traffic_density_2014.tif')
    raster = grid.copy()
    raster.reproject(_r)
    raster.positive()
    if truncate is not None:
        raster[raster < truncate] = 0
    raster.lognorm()
    return raster


def get_flying(grid, truncate=None):
    l = Layer.objects.get(name='ptm_13_complete')
    raster = layers_to_raster([l], grid, 'PTM_13')
    if truncate is not None:
        raster[raster < truncate] = 0
    raster.lognorm()
    #raster.norm()
    return raster


def get_trawling_gsa(grid, truncate=None):
    l = Layer.objects.get(name='gsa17_18_otb13')
    raster = layers_to_raster([l], grid, 'OTB_13')
    if truncate is not None:
        raster[raster < truncate] = 0
    raster.lognorm()
    #raster.norm()
    return raster


def get_trawling3(grid):
    l = Layer.objects.get(name='v_recode_fish_area_clean')
    raster = layers_to_raster([l], grid, 'value')
    # raster.lognorm()
    raster.norm()
    return raster


def get_trawling2(grid):
    _r = rg.read_raster('/usr/share/geoserver/data/data/geonode/number_ais_clip/number_ais_clip.geotiff')
    raster = grid.copy()
    raster.reproject(_r)
    # raster.lognorm()
    return raster


def get_trawling(grid):
    # TODO: manca il layer 2174 Bottom otter trawl fishery GSA 20 - 2013

    # 2402 ptm_13  "Pair pelagic trawl fishery - 2013"
    # http://data.adriplan.eu/layers/geonode%3Aptm_13
    l = Layer.objects.get(pk=2402)
    r1 = layers_to_raster([l], grid, 'ptm_13_n')
    r1.norm()

    # 2121 gsa17_18_otb13 Bottom otter trawl fishery GSA 17 and 18 - 2013
    # http://data.adriplan.eu/layers/geonode%3Agsa17_18_otb13
    l = Layer.objects.get(pk=2121)
    r2 = layers_to_raster([l], grid, 'OTB_13')

    # 2092 gsa19_otb13 Bottom otter trawl fishery GSA 19 - 2013
    # http://data.adriplan.eu/layers/geonode%3Agsa19_otb13
    l = Layer.objects.get(pk=2121)
    r3 = layers_to_raster([l], grid, 'OTB_13')

    r23 = np.fmax(r2, r3)
    r23.norm()

    l4 = Layer.objects.get(name='otb_2013fe_clean')
    r4 = layers_to_raster([l4], grid, 'Count')
    r4.norm()

    r123 = r1 + r23 + r4
    r123.norm()
    return r123


def get_small_scale_fishery_01_12(grid):
    # Small scale fishery VL 01-12 cleaned
    r1 = layer_to_raster(2175, grid, column='GRIDCODE')
    r1[r1 == 0] = 6

    # revert value
    _r1 = 6 - r1

    _r1.norm()

    return _r1


def get_small_scale_fishery(grid):
    # Small scale fishery VL 01-12 cleaned
    r1 = layer_to_raster(2175, grid, column='GRIDCODE')
    r1[r1 == 0] = 6

    #  Small scale fishery VL 12-24 cleaned
    r2 = layer_to_raster(2217, grid, column='GRIDCODE')
    r2[r2 == 0] = 6

    # revert value
    _r1 = 6 - r1
    _r2 = 6 - r2

    r12 = _r1 + _r2
    r12.norm()

    return r12


def availability_to_raster(layers, grid):
    features = []
    for l in layers:
        for da in l.data_availability_areas.all():
            feature = shape(simplejson.loads(da.geo.json)).buffer(0)
            features.append(feature)

    gdf = GeoDataFrame({'geometry': features, 'val': 1.},
                       geometry="geometry",
                       crs={'init': 'epsg:4326'})
    if gdf.shape[0] > 0:
        raster = rg.read_df_like(grid, gdf, column='val')
        return raster
    return None


def layers_to_raster(layers, grid, column=None, compute_area=False, value=1.):
    raster = np.zeros_like(grid)

    for l in layers:
        raster.patch(layer_to_raster(l, grid, column=column, value=value,
                                     compute_area=compute_area))
    # raster.set_mask(~grid._array.astype(bool))
    return raster


def layer_to_raster(l, grid=None, res=None, **kwargs):
    if isinstance(l, int):
        l = Layer.objects.get(pk=l)

    gdf = None

    if hasattr(l, 'name'):
        if l.typename == 'geonode:traffic_density_2014':
            _r = rg.read_raster('/var/www/geonode/uploaded/layers/traffic_density_2014.tif')
            raster = grid.copy()
            raster.reproject(_r)
            raster.positive()
            print "OLD TRAFFIC"
            return raster
        elif l.typename == 'geonode:traffic_density_lines_gener_2014_2015_ais_3857_nocolor':
            _r = rg.read_raster('/var/www/geonode/uploaded/layers/traffic_density_lines_gener_2014_2015_ais_3857_nocolor.tiff')
            raster = grid.copy()
            raster.reproject(_r.astype(np.float))
            raster.positive()
            print "NEW TRAFFIC"
            return raster
        elif l.name in ['lba_pressure_plume_threshold',
                        'lba_pressure_om',
                        'lba_pressure_nptot']:
            _r = rg.read_raster('/var/www/geonode/uploaded/layers/{}.tiff'.format(l.name), masked=True)
            _r[:] = _r.filled(0)
            raster = grid.copy()
            raster.reproject(_r)
            return raster
        if not l.is_vector():
            raise Exception("RASTER is not implemented")
        gdf = get_df(l.name)
    elif isinstance(l, str) or isinstance(l, unicode):
        gdf = get_df(l)
    if grid is not None:
        raster = rg.read_df_like(grid, gdf, **kwargs)
    else:
        raster = rg.read_df(gdf, res, **kwargs)
    return raster


def get_df(lname):
    conn = get_connection('datastore')

    gc_df = pd.read_sql('select * from geometry_columns',
                        conn, index_col = 'f_table_name')
    srid = gc_df.loc[lname].srid
    gtype = gc_df.loc[lname].type
    gname = gc_df.loc[lname].f_geometry_column

    if gtype in ('POLYGON', 'MULTIPOLYGON'):
        sql = "select *, st_buffer({}, 0) as the_geom_clean from {} where {} is not null".format(gname, lname, gname)
    else:
        sql = "select *, {} as the_geom_clean from {} where {} is not null".format(gname, lname, gname)
    # print sql
    gdf = GeoDataFrame.from_postgis(sql, conn, geom_col='the_geom_clean',
                                    crs={'init': 'epsg:{}'.format(srid), 'no_defs': True})
    # print lname, srid
    gdf.to_crs(epsg="3035", inplace=True)
    return gdf


def get_ci_result_by_uses(ci_id, result_uses, result_envs):
    cellsize = 1000
    result_ci = {}
    cics, uses, envs = _get_adriplan_cics(ci_id)

    combs = list(itertools.product(uses, envs))
    for p in combs:
        use = p[0]
        env = p[1]

        sens = get_sensitivities_by_rule(use, env)
        if env in result_envs and use in result_uses:
            for s in sens:
                distance = s.distance


                # convoluzione gaussiana
                if distance > 0:
                    sigma = distance / cellsize / 2.
                    usec = scipy.ndimage.gaussian_filter(result_uses[use],
                                                         sigma)
                else:
                    usec = result_uses[use]

                # print use, env, s, distance, distance / cellsize / 3.

                # normalization
                usec = usec / usec.max()

                sensarray = usec * result_envs[env] * s.total_score
                if use not in result_ci:
                    result_ci[use] = sensarray
                else:
                    result_ci[use] += sensarray

    return result_ci


def get_ci_result_by_envs(ci_id, result_uses, result_envs):
    cellsize = 1000
    result_ci = {}
    cics, uses, envs = _get_adriplan_cics(ci_id)

    combs = list(itertools.product(uses, envs))
    for p in combs:
        use = p[0]
        env = p[1]

        sens = get_sensitivities_by_rule(use, env)
        if env in result_envs and use in result_uses:
            for s in sens:
                distance = s.distance


                # convoluzione gaussiana
                if distance > 0:
                    sigma = distance / cellsize / 2.
                    usec = scipy.ndimage.gaussian_filter(result_uses[use],
                                                         sigma)
                else:
                    usec = result_uses[use]

                # print use, env, s, distance, distance / cellsize / 3.

                # normalization
                usec = usec / usec.max()

                sensarray = usec * result_envs[env] * s.total_score
                if env not in result_ci:
                    result_ci[env] = sensarray
                else:
                    result_ci[env] += sensarray

    return result_ci


def get_sensitivities(ci_id):
    cics, uses, envs = _get_adriplan_cics(ci_id)

    combs = list(itertools.product(uses, envs))
    df = pd.DataFrame(columns=('use', 'use_id',
                               'env', 'env_id',
                               'pres', 'pres_id',
                               'score', 'distance', 'confidence'))
    r = 0
    for p in combs:
        use = p[0]
        env = p[1]

        # sens = Sensitivity.objects.filter(activity_and_use=use,
        #                                   evironmental_component=env)
        sens = get_sensitivities_by_rule(use, env)
        for s in sens:
            distance = s.distance
            df.loc[r] = [use.label, use.id,
                         env.label, env.id,
                         s.pressure.label, s.pressure.id,
                         s.total_score, distance, s.confidence]
            r += 1
    return df


def get_cs_area(ci_id, to_srs):
    ci = CICaseStudy.objects.get(pk=ci_id)
    ci.area_of_interest.transform(to_srs)
    geo = shape(simplejson.loads(ci.area_of_interest.geojson))
    # geo = MultiPolygon(aimg.the_geom)
    return geo


def get_aim(to_srs):
    # aiml = Layer.objects.get(typename='geonode:adriplan_focus_areas')
    # aim = get_model(aiml)
    # aimg = aim.objects.all()[1]

    aiml = Layer.objects.get(typename='geonode:aim')
    aim = get_model(aiml)
    aimg = aim.objects.all()[0]

    aimg.the_geom.transform(to_srs)
    geo = shape(simplejson.loads(aimg.the_geom.geojson))
    # geo = MultiPolygon(aimg.the_geom)
    return geo


def get_territorialsea(grid):
    l = Layer.objects.get(name='legalstatus_all')
    raster = layers_to_raster([l], grid, 'id')
    return raster


def get_italianterritorialsea(grid):
    l = Layer.objects.get(name='legalstatus_all')
    raster = layers_to_raster([l], grid, 'fid')
    raster[raster != 872] = 0
    raster[raster == 872] = 1
    l = Layer.objects.get(name='legalstatus_all')
    _raster = layers_to_raster([l], grid, 'id')
    raster[_raster == 2] = 1
    return raster


def get_adriatic_grid(to_srs):
    _adriatic = DataAvailabilityArea.objects.get(pk=13)
    _adriatic.geo.transform(to_srs)
    geo = shape(simplejson.loads(_adriatic.geo.geojson))

    return rg.read_features([geo], 1000, 3035, eea=True)


def get_adriatic_italy_grid(to_srs):
    _adriatic = DataAvailabilityArea.objects.get(pk=1)
    _adriatic.geo.transform(to_srs)
    geo = shape(simplejson.loads(_adriatic.geo.geojson))

    return rg.read_features([geo], 1000, 3035, eea=True)


def get_rer_geo(to_srs):
    rerl = Layer.objects.get(typename='geonode:rer_project_area')
    rer = get_model(rerl)
    geo = None
    for _d in rer.objects.all():
        _d.the_geom.transform(to_srs)
        if geo is None:
            geo = _d.the_geom
        else:
            geo = geo.union(_d.the_geom)
    return geo


def get_rer_500_grid(to_srs):
    geo = get_rer_geo(to_srs)
    geos = [(shape(simplejson.loads(geo.geojson)), 1)]
    return rg.read_features(geos, 500, 3035, eea=True)


def get_abruzzo_molise_adriatic_apulia_grid(to_srs):
    geos = []
    for _d in DataAvailabilityArea.objects.filter(pk__in=(16, 17, 20)):
        _d.geo.transform(to_srs)
        geos.append(shape(simplejson.loads(_d.geo.geojson)))

    return rg.read_features(geos, 1000, 3035, eea=True)


def get_conflict_by_uses(use1, use2):
    if isinstance(use1, int):
        use1 = ActivityAndUse.objects.get(pk=use1)
    if isinstance(use2, int):
        use2 = ActivityAndUse.objects.get(pk=use2)

    vscale1 = use1.vertical_scale.value
    vscale2 = use2.vertical_scale.value
    # Rule 1
    if vscale1 != 3 and vscale2 != 3 and vscale1 != vscale2:
        return 0
    mobility1 = use1.mobility.value
    mobility2 = use2.mobility.value
    spatial1 = use1.spatial_scale.value
    spatial2 = use2.spatial_scale.value
    time1 = use1.time_scale.value
    time2 = use2.time_scale.value
    # Rule 2
    if mobility1 and mobility2:
        return min(spatial1, spatial2) + min(time1, time2)
    # Rule 3
    return max(spatial1, spatial2) + max(time1, time2)


def get_sensitivities_by_rule(use, env):
    if isinstance(use, int):
        use = ActivityAndUse.objects.get(pk=use)
    if isinstance(env, int):
        env = EnvironmentalComponent.objects.get(pk=env)
    sens = Sensitivity.objects.filter(activity_and_use=use,
                                      evironmental_component=env)

    # return sens
    _sens = []

    # Rule 1, 2, 3
    # if len(_sens) < 2:
    responses = []
    for s in sens:
        responses.append((s,
                          s.number_of_scores,
                          s.confidence,
                          s.total_score
                      ))
    responses = sorted(responses,
                       key=operator.itemgetter(1, 2, 3),
                       reverse=True)

    # Rule 0
    generic_pressures = Pressure.objects.filter(label__istartswith='generic')
    for s in sens:
        if s.pressure in generic_pressures:
            _sens.append(s)

    _sens = [r[0] for r in responses] + _sens

    return _sens[:2]


def weighted_quantile(values, quantiles, sample_weight=None, values_sorted=False, old_style=False):
    """ Very close to numpy.percentile, but supports weights.
    NOTE: quantiles should be in [0, 1]!
    :param values: numpy.array with data
    :param quantiles: array-like with many quantiles needed
    :param sample_weight: array-like of the same length as `array`
    :param values_sorted: bool, if True, then will avoid sorting of initial array
    :param old_style: if True, will correct output to be consistent with numpy.percentile.
    :return: numpy.array with computed quantiles.
    """
    values = np.array(values)
    quantiles = np.array(quantiles)
    if sample_weight is None:
        sample_weight = np.ones(len(values))
    sample_weight = np.array(sample_weight)
    assert np.all(quantiles >= 0) and np.all(quantiles <= 1), 'quantiles should be in [0, 1]'

    if not values_sorted:
        sorter = np.argsort(values)
        values = values[sorter]
        sample_weight = sample_weight[sorter]

    weighted_quantiles = np.cumsum(sample_weight) - 0.5 * sample_weight
    if old_style:
        # To be convenient with np.percentile
        weighted_quantiles -= weighted_quantiles[0]
        weighted_quantiles /= weighted_quantiles[-1]
    else:
        weighted_quantiles /= np.sum(sample_weight)
    return np.interp(quantiles, weighted_quantiles, values)


def raster_file_upload(filepath, **kwargs):
    data = rg.read_raster(filepath)
    layer = file_upload(filepath, overwrite=True, **kwargs)
    _sld = get_sld(data, layer.name)
    cat = gs_catalog
    style = cat.get_style(layer.name)
    style.update_body(_sld)
    return layer, style


def get_sld(data, name):
    vmax = data.max()
    vmean = vmax / 2.
    return RASTER_SLD.format(name=name, vmax=vmax, vmean=vmean)

RASTER_SLD = """<?xml version="1.0" encoding="UTF-8"?>
<sld:StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:sld="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:gml="http://www.opengis.net/gml" version="1.0.0">
  <sld:NamedLayer>
    <sld:Name>{name}</sld:Name>
    <sld:UserStyle>
      <sld:Name>{name}</sld:Name>
      <sld:Title>{name}</sld:Title>
      <sld:FeatureTypeStyle>
        <sld:Name>name</sld:Name>
        <sld:Rule>
          <RasterSymbolizer>
          <Opacity>1.0</Opacity>
            <ColorMap type="ramp">
              <ColorMapEntry opacity="0" color="#0000ff" quantity="0"/>
              <ColorMapEntry color="#0000ff" quantity="0.00001"/>
              <ColorMapEntry color="#ffff00" quantity="{vmean}"/>
              <ColorMapEntry color="#ff0000" quantity="{vmax}"/>
              <ColorMapEntry opacity="0" color="#ff0000" quantity="{vmax}"/>
          </ColorMap>
          </RasterSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </sld:NamedLayer>
</sld:StyledLayerDescriptor>"""
