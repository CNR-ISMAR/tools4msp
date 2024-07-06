import logging
from os import listdir, path, makedirs
from slugify import slugify
import pandas as pd
import geopandas as gpd
import numpy as np
try:
    import rectifiedgrid as rg
except:
    pass
import json

try:
    from rasterio.warp import RESAMPLING as Resampling
except ImportError:
    from rasterio.enums import Resampling

logger = logging.getLogger('tools4msp.casestudy')


def read_casestudy(csmetadata):
    ""
    # read metadata
    with open(csmetadata) as data_file:
        meta = json.load(data_file)

        c = CaseStudyBase(None, meta['basedir'], meta['name'])
        c.load_grid()
        c.load_layers()
        c.load_inputs()
        c.layer_preprocessing()
        return c
    return None


def aggregate_layers_to_gdf(layers, step=1, melt=False):
    grid = layers.get('GRID') 
    bounds = grid.bounds
    resolution = grid.resolution
    xcoords = np.linspace(bounds[0]+resolution/2, bounds[2]-resolution/2, grid.shape[1])
    # y is in reverse order
    ycoords = np.linspace(bounds[3]-resolution/2, bounds[1]+resolution/2, grid.shape[0])    
    arr1 = np.meshgrid(xcoords[::step], ycoords[::step])
    arr1x = np.ravel(arr1[0])
    arr1y = np.ravel(arr1[1])
    df1 = pd.DataFrame({'X':arr1x, 'Y':arr1y})
    gdf = gpd.GeoDataFrame(
            df1, geometry=gpd.points_from_xy(df1.X, df1.Y), crs="epsg:3035")
    
    gdf['GRID'] = grid[::step,::step].flatten()
    for cname, l in layers.items():
        gdf[cname] = l[::step,::step].flatten()
    gdf = gdf[gdf.GRID>0]
    # gdf = gpd.GeoDataFrame()

    # for idx, l in layers.iterrows():
    #     _r = l['layer']
    #     stats = zonal_stats(grid, _r.values, affine=_r.rio.transform())
    #     _df[cname] = [a['mean'] for a in stats]
    if melt:
        col = gdf.columns[~gdf.columns.isin(['GRID', 'X','Y','geometry'])]
        gdf = gdf.melt(id_vars="geometry", value_vars=col)
        gdf = gdf[gdf.value!=0].set_geometry('geometry', crs="epsg:3035")
    return gdf

class CaseStudyBase(object):
    """Class to implement Tools4MSP CaseStudy.
    name: CaseStudy name

    version: CaseStudy version. A version identifis an input dataset
    (i.e. use and env layers, area)

    rtype: aka run. A CaseStudy can have multiple run. A run can
    specify a specific tool, a subset of area and a subset of use and
    env layers.

    """
    def __init__(self,
                 csdir=None,
                 rundir=None,
                 name='unnamed'):
        self.name = name
        #
        self.grid = None
        self.outputgrid = None
        self.csdir = csdir
        self.rundir = rundir

        self.set_dirs()

        columns = ['code', 'code_group', 'layer', 'availability']
        self.layers = pd.DataFrame(columns=columns)

        columns = ['code', 'code_group', 'input']
        self.inputs = pd.DataFrame(columns=columns)

        self.outputs = {}

        self.layer_preprocessed = False
        
        # store last runtypelevel
        # None: no run has been performed or the child module doesn't support runtypelevel parameter
        # 1: only main output
        # 3: default level of outputs. This is sufficient to perform Uncertainty and Sensitivity analysis
        self.runtypelevel = None

    def get_outpath(self, code, outtype, extension=None):
        path = [self.csdir, outtype, code]
        if extension is not None:
            path.append(".{}".format(extension))
        return '/'.join(path)

    def set_metadata(self):
        self.metadata['name'] = self.name
        self.metadata['version'] = self.version

    def set_dirs(self):
        self.layersdir = path.join(self.csdir, 'layers')
        self.inputsdir = path.join(self.csdir, 'inputs')

        return
        # self.default_cs_basedir = path.join(self.basedir, self.name, self.version, 'full') + '/'
        # self.cs_basedir = path.join(self.basedir, self.name, self.version, self.rtype) + '/'
        # self.datadir = path.join(self.basedir, self.name, self.version, 'datadir') + '/'
        #
        # if not path.exists(self.cs_basedir):
        #     makedirs(self.cs_basedir)
        # if not path.exists(self.datadir):
        #     makedirs(self.datadir)

    def add_layer(self, layer, code, code_group, availability=None):
        self.layers.loc[code, 'code'] = code
        self.layers.loc[code, 'code_group'] = code_group
        self.layers.loc[code, 'layer'] = layer
        self.layers.loc[code, 'availability'] = availability
        logger.debug("loaded layer {} minval={} maxval={} shape={}".format(code, np.nanmin(layer), np.nanmax(layer), layer.shape))
        return code

    def get_envs(self):
        return self.layers[self.layers.code_group == 'env']

    def get_uses(self):
        return self.layers[self.layers.code_group == 'use']

    def get_layer(self, lid):
        if lid in self.layers.index:
            return self.layers.loc[lid]
        # search by label
        if lid in self.layers.code.values:
            return self.layers[self.layers.code == lid].iloc[0]
        return None

    def n_uses(self):
        raster = self.grid.copy()
        raster = 0.
        for _l in self.get_uses().iterrows():
            raster[_l.layer > 0] += 1
        return raster

    def n_envs(self):
        raster = self.grid.copy()
        raster = 0.
        for _l in self.get_envs().iterrows():
            raster[_l.layer > 0] += 1
        return raster

    def availability(self):
        raster = self.grid.copy()
        raster = 0.
        for _l in self.layers.iterrows():
            raster[_l.layer > 0] += 1
        return raster

    def dump_layers(self, lid=None):
        """Save the layers on 'datadir' directory."""
        if self.datadir is None:
            raise Exception("datadir is not configured: cannot save the data")
        for idx, layer in self.layers.iterrows():
            layerpath = self.datadir + idx
            layer.layer.write_raster(layerpath)
            #
            av_layerpath = self.datadir + 'av_' + idx
            if layer.availability is not None:
                layer.availability.write_raster(av_layerpath)
        # dump metadata
        mddf = self.layers[['lid', 'label', 'msptype', 'ltype',]]
        mddf.to_csv(self.datadir + 'layersmd.csv')

    def load_layers(self, code=None, availability=False):
        """Load the layers from 'layersdir' directory."""
        layerref = {}
        if self.layersdir is None:
            raise Exception("layersdir is not configured: cannot load the data")
        if not path.isdir(self.layersdir):
            raise FileNotFoundError("Directory layersdir doesn't exist:", self.layersdir)
        for f in listdir(self.layersdir):
            fname, ext = path.splitext(f)
            if ext == '.geotiff' or ext == '.tiff' or ext == '.tif':
                # remove random file suffix
                fname = fname.split('_')[0]
                code_group, _code = fname.split('-', 1)
                layerref[_code] = {'f': f,
                                   'code_group': code_group
                                   }

        if code is not None:
            if code not in layerref.keys():
                return False
            _r = self.read_raster(layerref[code]['f']).fill_underlying_data(0)
            _r.crs = rg.utils.parse_projection('epsg:3035') 
            self.add_layer(_r,
                           code,
                           layerref[code]['code_group'],
                           availability=None)
            return True

        for _code, fpath in layerref.items():
            if availability:
                # TODO
                pass
            else:
                raster = None
            _r = self.read_raster(layerref[_code]['f']).fill_underlying_data(0)
            _r.crs = rg.utils.parse_projection('epsg:3035')
            self.add_layer(_r,
                           _code,
                           layerref[_code]['code_group'],
                           availability=None)
        # TODO: manage error on loading
        return True

    def read_raster(self, fname):
        filepath = path.join(self.layersdir, fname)
        return rg.read_raster(filepath)

    def dump_inputs(self):
        # self.dump_layers()

        self.grid.write_raster(self.datadir + 'domain_area_dataset.tiff')

    def dump_outputs(self):
        pass

    def load_grid(self):
        self.grid = self.layers.loc[self.layers.code == 'GRID']['layer'].values[0]

    def get_grid(self):
        if self.grid is not None:
            return self.grid
        self.load_layers('GRID')
        self.load_grid()
        return self.grid

    def get_outputgrid(self):
        if self.outputgrid is not None:
            return self.outputgrid
        if self.load_layers('OUTPUTGRID'):
            self.outputgrid = self.layers.loc[self.layers.code == 'OUTPUTGRID']['layer'].values[0]
        return self.outputgrid

    def get_input_paths(self):
        # if self._input_paths is not None:
        #    return self._input_paths
        inputs_paths = {}
        for f in listdir(self.inputsdir):
            filepath = path.join(self.inputsdir, f)
            fname, ext = path.splitext(f)
            if ext == '.json':
                # remove random file suffix
                fname = fname.split('_')[0]
                inputs_paths[fname] = filepath
        # self._input_paths = inputs_paths
        return inputs_paths

    def load_input(self, fname):
        inputs_paths = self.get_input_paths()
        filepath = inputs_paths.get(fname)
        if filepath is not None:
            return pd.read_json(filepath)
        return None

    def load_inputs(self):
        self.layer_weights = self.load_input('casestudy-LAYER-WEIGHTS')
        self.load_grid()

    def set_mask(self, mask, overwrite=True):
        """Apply a mask to grid, all layers and availability areas"""
        self.grid.mask = mask.copy()
        for idx, l in self.layers.iterrows():
            if overwrite:
                l.layer.mask = np.ma.nomask
                l.layer.mask = mask.copy()
            else:
                l.layer[mask] = np.ma.masked
            #
            if l.availability is not None:
                if overwrite:
                    l.availability.mask = np.ma.nomask
                    l.availability.mask = mask.copy()
                else:
                    l.availability[mask] = np.ma.masked

    def set_grid(self, grid, resampling=Resampling.nearest):
        """Reproject the self on the new grid"""
        self.grid = grid.copy()
        for idx, l in self.layers.iterrows():
            _l = self.grid.copy()
            _l.reproject(l.layer, resampling)
            l.layer = _l
            l.layer[self.grid == 0] = np.ma.masked
            #
            if l.availability is not None:
                _v = self.grid.copy()
                _v.reproject(l.availability)
                l.availability = _v
                l.availability[self.grid == 0] = np.ma.masked

    def layer_preprocessing(self, force=False):
        if self.layer_preprocessed and not force:
            return True
        if self.layer_weights is not None:
            weights = self.layer_weights.pivot('layer', 'param', 'weight')
            def _get_value(layer, param, default=None):
                try:
                    return weights.at[layer, param]
                except KeyError:
                    return default
            for idx, l in self.layers.iterrows():
                layer = l.layer
                rescale_mode = _get_value(l.code, 'RESCALE-MODE')
                weight_frequency = _get_value(l.code, 'WEIGHT-FREQUENCY', 1)
                weight_magnitude = _get_value(l.code, 'WEIGHT-MAGNITUDE', 1)
                weight_relevance = _get_value(l.code, 'WEIGHT-RELEVANCE', 1)
                layer_weight = weight_frequency * weight_magnitude * weight_relevance
                
                if rescale_mode == 'none':
                    pass
                elif rescale_mode == 'rescale':
                    layer = layer.norm(copy=True)
                elif rescale_mode == 'log':
                    layer = layer.log(copy=True)
                elif rescale_mode == 'logrescale':
                    layer = layer.lognorm(copy=True)
                elif rescale_mode == 'normlog':
                    layer = (layer.norm(copy=True) * 100).log(copy=True)
                elif rescale_mode == 'normlogrescale':
                    layer = (layer.norm(copy=True) * 100).lognorm(copy=True)
                elif rescale_mode == 'pa':
                    layer = layer.copy()
                    layer[~(layer.mask) & (layer > 0)] = 1
                                                                                                
                if layer_weight is not None:
                    layer = layer.copy() * layer_weight
                    print("APPLY layer weights")
                    print(layer.max())

                self.layers.loc[idx, 'layer'] = layer
            self.layer_preprocessed = True
