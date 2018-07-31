from __future__ import absolute_import

import logging
from os import path
from os import makedirs
from slugify import slugify
import pandas as pd
import numpy as np
import rectifiedgrid as rg
import json
from rasterio.warp import reproject, RESAMPLING

from .ci import CumulativeImpactMixin
from .ci_3_0 import CumulativeImpactMixin as CumulativeImpactMixin3
from .conflict_score import ConflictScoreMixin

logger = logging.getLogger('tools4msp.casestudy')


def read_casestudy(csmetadata):
    ""
    # read metadata
    with open(csmetadata) as data_file:
        meta = json.load(data_file)

        c = CaseStudy(None, meta['basedir'], meta['name'])
        c.load_grid()
        c.load_layers()
        c.load_inputs()
        return c
    return None


class CaseStudy(CumulativeImpactMixin, ConflictScoreMixin):
    """Class to implement Tools4MSP CaseStudy.
    name: CaseStudy name

    version: CaseStudy version. A version identifis an input dataset
    (i.e. use and env layers, area)

    rtype: aka run. A CaseStudy can have multiple run. A run can
    specify a specific tool, a subset of area and a subset of use and
    env layers.

    """
    def __init__(self, grid, basedir=None,
                 name='unnamed', version='v1', rtype='full'):
        self.name = name
        self.version = version
        self.rtype = rtype
        #
        self.grid = grid
        self.basedir = basedir

        self.set_dirs()

        columns = ['lid', 'label', 'msptype', 'ltype', 'layer',
                   'source', 'availability']
        self.layers = pd.DataFrame(columns=columns)

        self.outputs = {}

        super(CaseStudy, self).__init__(grid, basedir=basedir,
                                        name='unnamed', version='v1', rtype='full')

    def get_outfile(self, fname, rtype=None):
        if rtype is None:
            rtype = self.rtype
        return 'tools4msp-{}-{}-{}-{}'.format(self.name, self.version, rtype, fname)

    def set_metadata(self):
        self.metadata['name'] = self.name
        self.metadata['version'] = self.version

    def get_outpath(self, fname, rtype=None):
        if rtype is None:
            _cs_basedir = self.cs_basedir
        else:
            _cs_basedir = path.join(self.basedir, self.name, self.version, rtype) + '/'

        return path.join(_cs_basedir, self.get_outfile(fname, rtype=rtype))

    def set_dirs(self):
        self.default_cs_basedir = path.join(self.basedir, self.name, self.version, 'full') + '/'
        self.cs_basedir = path.join(self.basedir, self.name, self.version, self.rtype) + '/'
        self.datadir = path.join(self.basedir, self.name, self.version, 'datadir') + '/'

        if not path.exists(self.cs_basedir):
            makedirs(self.cs_basedir)
        if not path.exists(self.datadir):
            makedirs(self.datadir)

    def add_layer(self, layer, msptype, lid=None, label=None, availability=None):
        if lid is None:
            if label is None:
                lid = self.layers.shape[0]
            else:
                lid = slugify(label)
        if label is None:
            label = lid
        self.layers.loc[lid, 'lid'] = lid
        self.layers.loc[lid, 'label'] = label
        self.layers.loc[lid, 'msptype'] = msptype
        self.layers.loc[lid, 'layer'] = layer
        self.layers.loc[lid, 'availability'] = availability
        return lid

    def get_envs(self):
        return self.layers[self.layers.msptype == 'env']

    def get_uses(self):
        return self.layers[self.layers.msptype == 'use']

    def get_layer(self, lid):
        if lid in self.layers.index:
            return self.layers.loc[lid]
        # search by label
        if lid in self.layers.label.values:
            return self.layers[self.layers.label == lid].iloc[0]
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
            print layer.label, layerpath
            layer.layer.write_raster(layerpath)
            #
            av_layerpath = self.datadir + 'av_' + idx
            if layer.availability is not None:
                layer.availability.write_raster(av_layerpath)
        # dump metadata
        mddf = self.layers[['lid', 'label', 'msptype', 'ltype',]]
        mddf.to_csv(self.datadir + 'layersmd.csv')

    def load_layers(self, lid=None, availability=False):
        """Load the layers from 'datadir' directory."""
        if self.datadir is None:
            raise Exception("datadir is not configured: cannot load the data")

        # read metadata
        _layers = pd.read_csv(self.datadir + 'layersmd.csv', index_col=0)

        if lid is not None:
            layer = _layers.loc[lid]
            if availability:
                raster = self.read_raster('av_' + lid)
            else:
                raster = None
            self.add_layer(self.read_raster(lid),
                           layer.msptype,
                           lid=lid,
                           label=layer.label,
                           availability=raster)
            return True

        for lid, layer in _layers.iterrows():
            if availability:
                raster = self.read_raster('av_' + lid)
            else:
                raster = None
            self.add_layer(self.read_raster(lid),
                           layer.msptype,
                           lid=lid,
                           label=layer.label,
                           availability=raster)
        # TODO: manage error on loading
        return True

    def read_raster(self, lid=None):
        """Read a raster from 'datadir'."""
        if self.datadir is None:
            return None
            # raise Exception("datadir is not configured: cannot load the data")

        layerpath = self.datadir + lid
        return rg.read_raster(layerpath)

    def dump_inputs(self):
        # self.dump_layers()

        self.grid.write_raster(self.datadir + 'grid.tiff')

        super(CaseStudy, self).dump_inputs()

    def dump_outputs(self):
        super(CaseStudy, self).dump_outputs()

    def load_grid(self):
        self.grid = rg.read_raster(self.datadir + 'grid.tiff')

    def load_inputs(self):
        self.load_grid()
        super(CaseStudy, self).load_inputs()

    def set_mask(self, mask):
        """Apply a mask to grid, all layers and availability areas"""
        self.grid.mask = mask.copy()
        for idx, l in self.layers.iterrows():
            l.layer.mask = np.ma.nomask
            l.layer.mask = mask.copy()
            #
            if l.availability is not None:
                l.availability.mask = np.ma.nomask
                l.availability.mask = mask.copy()

    def set_grid(self, grid, resampling=RESAMPLING.nearest):
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


class CaseStudy3(CumulativeImpactMixin3, ConflictScoreMixin):
    """Class to implement Tools4MSP CaseStudy.
    name: CaseStudy name

    version: CaseStudy version. A version identifis an input dataset
    (i.e. use and env layers, area)

    rtype: aka run. A CaseStudy can have multiple run. A run can
    specify a specific tool, a subset of area and a subset of use and
    env layers.

    """
    def __init__(self, grid, basedir=None,
                 name='unnamed', version='v1', rtype='full'):
        self.name = name
        self.version = version
        self.rtype = rtype
        #
        self.grid = grid
        self.basedir = basedir

        self.set_dirs()

        columns = ['lid', 'label', 'msptype', 'ltype', 'layer',
                   'source', 'availability']
        self.layers = pd.DataFrame(columns=columns)

        self.outputs = {}

        super(CaseStudy3, self).__init__(grid, basedir=basedir,
                                        name='unnamed', version='v1', rtype='full')

    def get_outfile(self, fname, rtype=None):
        if rtype is None:
            rtype = self.rtype
        return 'tools4msp-{}-{}-{}-{}'.format(self.name, self.version, rtype, fname)

    def set_metadata(self):
        self.metadata['name'] = self.name
        self.metadata['version'] = self.version

    def get_outpath(self, fname, rtype=None):
        if rtype is None:
            _cs_basedir = self.cs_basedir
        else:
            _cs_basedir = path.join(self.basedir, self.name, self.version, rtype) + '/'

        return path.join(_cs_basedir, self.get_outfile(fname, rtype=rtype))

    def set_dirs(self):
        self.default_cs_basedir = path.join(self.basedir, self.name, self.version, 'full') + '/'
        self.cs_basedir = path.join(self.basedir, self.name, self.version, self.rtype) + '/'
        self.datadir = path.join(self.basedir, self.name, self.version, 'datadir') + '/'

        if not path.exists(self.cs_basedir):
            makedirs(self.cs_basedir)
        if not path.exists(self.datadir):
            makedirs(self.datadir)

    def add_layer(self, layer, msptype, lid=None, label=None, availability=None):
        if lid is None:
            if label is None:
                lid = self.layers.shape[0]
            else:
                lid = slugify(label)
        if label is None:
            label = lid
        self.layers.loc[lid, 'lid'] = lid
        self.layers.loc[lid, 'label'] = label
        self.layers.loc[lid, 'msptype'] = msptype
        self.layers.loc[lid, 'layer'] = layer
        self.layers.loc[lid, 'availability'] = availability
        return lid

    def get_envs(self):
        return self.layers[self.layers.msptype == 'env']

    def get_uses(self):
        return self.layers[self.layers.msptype == 'use']

    def get_layer(self, lid):
        if lid in self.layers.index:
            return self.layers.loc[lid]
        # search by label
        if lid in self.layers.label.values:
            return self.layers[self.layers.label == lid].iloc[0]
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
            print layer.label, layerpath
            layer.layer.write_raster(layerpath)
            #
            av_layerpath = self.datadir + 'av_' + idx
            if layer.availability is not None:
                layer.availability.write_raster(av_layerpath)
        # dump metadata
        mddf = self.layers[['lid', 'label', 'msptype', 'ltype',]]
        mddf.to_csv(self.datadir + 'layersmd.csv')

    def load_layers(self, lid=None, availability=False):
        """Load the layers from 'datadir' directory."""
        if self.datadir is None:
            raise Exception("datadir is not configured: cannot load the data")

        # read metadata
        try:
            _layers = pd.read_csv(self.datadir + 'layersmd.csv', index_col=0)
        except IOError:
            logger.warning('load_layers: layersmd file does not exist')
            return False

        if lid is not None:
            layer = _layers.loc[lid]
            if availability:
                raster = self.read_raster('av_' + lid)
            else:
                raster = None
            self.add_layer(self.read_raster(lid),
                           layer.msptype,
                           lid=lid,
                           label=layer.label,
                           availability=raster)
            return True

        for lid, layer in _layers.iterrows():
            if availability:
                raster = self.read_raster('av_' + lid)
            else:
                raster = None
            self.add_layer(self.read_raster(lid),
                           layer.msptype,
                           lid=lid,
                           label=layer.label,
                           availability=raster)
        # TODO: manage error on loading
        return True

    def read_raster(self, lid=None):
        """Read a raster from 'datadir'."""
        if self.datadir is None:
            return None
            # raise Exception("datadir is not configured: cannot load the data")

        layerpath = self.datadir + lid
        return rg.read_raster(layerpath)

    def dump_inputs(self):
        # self.dump_layers()

        self.grid.write_raster(self.datadir + 'grid.tiff')

        super(CaseStudy3, self).dump_inputs()

    def dump_outputs(self):
        super(CaseStudy3, self).dump_outputs()

    def load_grid(self):
        self.grid = rg.read_raster(self.datadir + 'grid.tiff')

    def load_inputs(self):
        self.load_grid()
        super(CaseStudy3, self).load_inputs()

    def set_mask(self, mask):
        """Apply a mask to grid, all layers and availability areas"""
        self.grid.mask = mask.copy()
        for idx, l in self.layers.iterrows():
            l.layer.mask = np.ma.nomask
            l.layer.mask = mask.copy()
            #
            if l.availability is not None:
                l.availability.mask = np.ma.nomask
                l.availability.mask = mask.copy()

    def set_grid(self, grid, resampling=RESAMPLING.nearest):
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
