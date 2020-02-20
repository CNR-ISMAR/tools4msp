import logging
from os import listdir, path, makedirs
from slugify import slugify
import pandas as pd
import numpy as np
import rectifiedgrid as rg
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
        return c
    return None


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
        self.csdir = csdir
        self.rundir = rundir

        self.set_dirs()

        columns = ['code', 'code_group', 'layer', 'availability']
        self.layers = pd.DataFrame(columns=columns)

        columns = ['code', 'code_group', 'input']
        self.inputs = pd.DataFrame(columns=columns)

        self.outputs = {}

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
        for f in listdir(self.layersdir):
            fname, ext = path.splitext(f)
            if ext == '.geotiff':
                code_group, _code = fname.split('-', 1)
                layerref[_code] = {'f': f,
                                   'code_group': code_group
                                   }

        if code is not None:
            self.add_layer(self.read_raster(layerref[code]['f']).fill_underlying_data(0),
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
            self.add_layer(self.read_raster(layerref[_code]['f']).fill_underlying_data(0),
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

    def load_inputs(self):
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
