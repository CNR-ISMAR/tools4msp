import sys
import tempfile
import logging
from os import path
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from django.contrib.gis.db import models
# TODO: make GeoNode dependency non mandatory
try:
    from geonode.layers.models import Layer
    geonode = True
except ImportError:
    geonode = False

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.functional import lazy
from django.utils.html import format_html
from django.core.files.base import ContentFile

import geopandas as gpd
from shapely import wkt
from shapely.ops import transform
import rectifiedgrid as rg

from jsonfield import JSONField
from .processing import Expression
from .utils import layer_to_raster, get_sensitivities_by_rule, get_conflict_by_uses, get_layerinfo
from .modules.casestudy import CaseStudyBase as CS, aggregate_layers_to_gdf
import itertools
import datetime
import hashlib
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db.models import F
from django.core.files import File
from io import StringIO
import json
from django.dispatch import receiver
import os
from .utils import write_to_file_field, plot_heatmap, get_sld, write_empty_file_field
from .plotutils import plot_map, get_map_figure_size, get_zoomlevel
from django.conf import settings
from .modules.cea import CEACaseStudy
from .modules.muc import MUCCaseStudy
from .modules.partrac import ParTracCaseStudy
from .modules.pmar import PMARCaseStudy
from .modules.geodatamaker import GeoDataMakerCaseStudy
from .modules.testmodule import TESTCaseStudy
from os import path
import pandas as pd
try:
    import cartopy
    import cartopy.io.img_tiles as cimgt
except:
    pass
import matplotlib.animation as animation
import numpy as np
# import rectifiedgrid as rg
from django.core.exceptions import ObjectDoesNotExist
import math
from .modules.sua import run_sua
import uuid
from treebeard.mp_tree import MP_Node, MP_NodeManager
from django_q.tasks import async_task, result
import shutil
import traceback

logger = logging.getLogger('tools4msp.models')

CODEDLABEL_GROUP_CHOICES = (
    ('casestudy', 'Case Study'),
    ('use', 'Activity & Uses'),
    ('env', 'Environmental receptor'),
    ('pre', 'Pressure'),
    ('usepre', 'Use-Pressure'),
    ('out', 'Outputs'),
    ('cea', 'CEA'),
    ('muc', 'MUC'),
    ('partrac', 'Particle tracking'),
    ('pmar', 'Pressure Assessment for Marine Activities'),
    ('testmodule', 'Test module'),
)

MODULE_TYPE_CHOICES = (
    ('cea', 'CEA'),
    ('muc', 'MUC'),
    ('partrac', 'Particle tracking'),
    ('pmar', 'Pressure Assessment for Marine Activities'),
    ('testmodule', 'Test module'),
    ('geodatamaker', 'GeoData Maker')
)

CASESTUDY_TYPE_CHOICES = (
    ('default', 'Default run'),
    ('customized', 'Customized run'),
)

VIZMODE_CHOICES = (
    (0, 'filtered'),
    (1, 'all'),
)


TOOLS4MSP_BASEDIR = '/var/www/geonode/static/cumulative_impact'

VISIBILITY_CHOICES = ((0, 'private'), (1, 'hidden'), (2, 'public'))

RUNSTATUS_CHOICES = ((0, 'running'), (1, 'completed'), (2, 'error'))

def get_coded_label_choices():
    lt = [("grid", "Analysis grid")]
    udata = []
    for u in Use.objects.all():
        udata.append((u.code, u.label))
    lt.append(('Uses', udata))

    return [
    ('Audio', (
            ('vinyl', 'Vinyl'),
            ('cd', 'CD'),
        )
    ),
    ('Video', (
            ('vhs', 'VHS Tape'),
            ('dvd', 'DVD'),
        )
    ),
    ('unknown', 'Unknown'),
]
    return lt


if not geonode:
    # fake model
    class Layer(models.Model):
        pass


class ClientApplication(models.Model):
    name = models.CharField(max_length=100)
    owner = models.OneToOneField('auth.User',
                                 on_delete=models.CASCADE,
                                 related_name="client_application_owner")
    users = models.ManyToManyField("auth.User",
                                   blank=True,
                                   help_text="Users registered by the client application",
                                   related_name="client_applications_user",
    )

    def __str__(self):
        return self.name


class Context(models.Model):
    """Model for storing information on data context."""
    label = models.CharField(max_length=100)
    description = models.CharField(max_length=800, null=True, blank=True)
    reference_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return self.label


def _run_sua(csr, nparams=20, nruns=100, bygroup=True, njobs=1, calc_second_order=False):
    if isinstance(csr, int):
        csr = CaseStudyRun.objects.get(pk=csr)
    selected_layers = csr.configuration['selected_layers']
    uses, pres, envs = check_coded_labels(selected_layers)
    kwargs_run = {'uses': uses, 'pressures': pres, 'envs': envs}
    module_cs = csr.casestudy.module_cs
    module_cs_sua = run_sua(module_cs, nparams=nparams,
                            nruns=nruns, bygroup=bygroup, njobs=njobs,
                            calc_second_order=calc_second_order,
                            kwargs_run=kwargs_run)

    module_cs_sua.cv[module_cs_sua.mean<0.01] = 0
    module_cs_sua.cv.mask = module_cs_sua.mean.mask.copy()
    
    layers = {'MAPCEA-SUA-MEAN': module_cs_sua.mean,
              'MAPCEA-SUA-CV': module_cs_sua.cv,}
    for code, l in layers.items():
        cl = CodedLabel.objects.get(code=code)
        # this override previous results
        csr_ol, created = csr.outputlayers.get_or_create(coded_label=cl)
        csr_ol.file = None
        csr_ol.thumbnail = None
        csr_ol.save()
        write_to_file_field(csr_ol.file, l.write_raster, 'tiff')
        plot_map(l, csr_ol.thumbnail, ceamaxval=None, logcolor=False)

    code = 'MAPCEA-SUA-SSA'
    cl = CodedLabel.objects.get(code=code)
    # this override previous results
    csr_o, created = csr.outputs.get_or_create(coded_label=cl)
    csr_o.file = None
    csr_o.thumbnail = None
    csr_o.save()

    data = []
    for df in module_cs_sua.analyze(calc_second_order=calc_second_order).to_df():
        data.append(df.reset_index().to_dict())
    write_to_file_field(csr_o.file, lambda buf: json.dump(data, buf), 'json', is_text_file=True)
    return module_cs

def run_wrapper(_csr, runtypelevel=3):
    run_result = {}
    if isinstance(_csr, int):
        csr = CaseStudyRun.objects.get(pk=_csr)
    else:
        csr = _csr

    run_result['csr_id'] = csr.pk
    try:
        csrid = _run(_csr, runtypelevel=runtypelevel)
        run_result['error'] = None
    except Exception as e:
        run_result['error'] = repr(e)
        traceback.print_exc()
    return run_result

def _run(_csr, runtypelevel=3):
    if isinstance(_csr, int):
        csr = CaseStudyRun.objects.get(pk=_csr)
    else:
        csr = _csr
        
    compute_aggregate_stats = False
    # if csr.owner.username == 'geoplatform____admin': # TODO: make it dynamic
    #    compute_aggregate_stats = True
    compute_aggregate_stats = False # force to False
        

    selected_layers = csr.configuration['selected_layers']
    module_cs = csr.casestudy.module_cs
    # search for outputgrid
    _outputgrid = csr.layers.filter(coded_label__code='OUTPUTGRID')
    if _outputgrid.count()==1:
        outputgrid = rg.read_raster(csr.layers.filter(coded_label__code='OUTPUTGRID')[0].file.path)
        module_cs.outputgrid = outputgrid
    uses, pres, envs = check_coded_labels(selected_layers)
    #
    pivot_layer = csr.configuration.get('pivot_layer', None)
    logger.debug('module {}'.format(csr.casestudy.module))
    if csr.casestudy.module == 'cea':
        logger.debug('loading layers, grid, inputs')
        module_cs.load_layers()
        # del csr.casestudy.module_cs
        # logger.debug('return')
        # return True
        module_cs.load_grid()
        module_cs.load_inputs()
        module_cs.layer_preprocessing()
        logger.debug('starting run')
        module_cs.run(uses=uses, envs=envs, pressures=pres, # usespres=usespres,
                      selected_layers=selected_layers, runtypelevel=runtypelevel)
        # start configuration of aggregate statistics
        if compute_aggregate_stats:
            aggregated_layers = {
            }
                    
        # Collect and save outputs
        logger.debug('collecting results')
        # CEASCORE map
        logger.debug('saving CEASCORE')
        ci = module_cs.outputs['ci']
        cl = CodedLabel.objects.get(code='CEASCORE')
        csr_ol = csr.outputlayers.create(coded_label=cl, description=cl.description)
        # print(np.nanmin(ci), np.nanmax(ci))
        write_to_file_field(csr_ol.file, ci.write_raster, 'tiff')
        if runtypelevel >= 3:
            logger.debug('plotting and saving thumbnail CEASCORE')
            # this is needed to exclude outliers
            plot_map(ci.crop(), csr_ol.thumbnail, # xlogcolor=True,
                     vmin=0, quantile_outliers=0.98)

        logger.debug('saving MAPINDEX-CEARANKING')
        cl = CodedLabel.objects.get(code='MAPINDEX-CEARANKING')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        # print(np.nanmin(ci), np.nanmax(ci))
        write_to_file_field(csr_ol.file, ci.write_raster, 'tiff')
        if runtypelevel >= 3:
            logger.debug('plotting and saving thumbnail MAPINDEX-CEARANKING')
            ci[ci.mask] = np.nan
            # plot_map(ci / ci.max()*100, csr_ol.thumbnail, logcolor=True)
            _colors = ['#016c59', '#1c9099', '#67a9cf', '#a6bddb', '#d0d1e6', '#f6eff7',
                       '#fef0d9', '#fdd49e', '#fdbb84', '#fc8d59', '#e34a33', '#b30000']
            _quantiles = [0, 0.05, 0.1, 0.2, 0.3, 0.4,
                          0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1]
            cmap = matplotlib.colors.ListedColormap(_colors)
            # bounds = ceascore.quantile([0, 0.5, 0.75, 0.9, 1]).data
            bounds = np.nanquantile(ci, _quantiles)
            bounds[-1] = np.nanmax(ci)
            norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
            logger.debug(np.nanmax(ci))
            logger.debug(bounds)
            logger.debug(ci>=bounds[0])
            plot_map(ci.masked_less(bounds[0], copy=True), csr_ol.thumbnail, # logcolor=True,
                     cmap=cmap, norm=norm)
            # 
            
        # return 
        if compute_aggregate_stats:
            aggregated_layers['CEASCORE'] = ci

        # # plot the pressures
        # for code, l in module_cs.outputs['pressures'].items():
        #     cl = CodedLabel.objects.get(code=code)
        #     csr_ol = csr.outputlayers.create(coded_label=cl)
        #     write_to_file_field(csr_ol.file, l.write_raster, 'tiff')
        #     plot_map(l, csr_ol.thumbnail)
        #     # set layerinfo
            
        #     csr_ol.description = csr_ol.layerinfo_str
        #     csr_ol.save()
        # * 100return
    
        # MAPCEA-IMPACT-LEVEL map
        logger.debug('saving MAPCEA-IMPACT-LEVEL')
        ci_impact_level = module_cs.outputs['ci_impact_level']
        cl = CodedLabel.objects.get(code='MAPCEA-IMPACT-LEVEL')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        # print(np.nanmin(ci), np.nanmax(ci))
        write_to_file_field(csr_ol.file, ci_impact_level.write_raster, 'tiff')
        if runtypelevel >= 3:
            logger.debug('plotting and saving thumbnail MAPCEA-IMPACT-LEVEL')
            plot_map(ci_impact_level, csr_ol.thumbnail, quantile_outliers=0.98)

        # MAPCEA-RECOVERY-TIME map
        logger.debug('saving MAPCEA-RECOVERY-TIME')
        ci_recovery_time = module_cs.outputs['ci_recovery_time']
        cl = CodedLabel.objects.get(code='MAPCEA-RECOVERY-TIME')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        # print(np.nanmin(ci), np.nanmax(ci))
        write_to_file_field(csr_ol.file, ci_recovery_time.write_raster, 'tiff')
        if runtypelevel >= 3:
            logger.debug('plotting and saving thumbnail MAPCEA-RECOVERY-TIME')
            plot_map(ci_recovery_time, csr_ol.thumbnail, quantile_outliers=0.98)

        # MAPINDEX-EDIV
        logger.debug('saving MAPINDEX-EDIV')
        mapindex_ediv = module_cs.outputs['mapindex_ediv']
        cl = CodedLabel.objects.get(code='MAPINDEX-EDIV')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        # print(np.nanmin(ci), np.nanmax(ci))
        write_to_file_field(csr_ol.file, mapindex_ediv.write_raster, 'tiff')
        if runtypelevel >= 3:
            logger.debug('plotting and saving thumbnail MAPINDEX-EDIV')
            plot_map(mapindex_ediv, csr_ol.thumbnail, logcolor=False)

        if compute_aggregate_stats:
            aggregated_layers['CEASCORE'] = ci

        # MAPINDEX-UDIV
        logger.debug('saving MAPINDEX-UDIV')
        mapindex_udiv = module_cs.outputs['mapindex_udiv']
        cl = CodedLabel.objects.get(code='MAPINDEX-UDIV')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        # print(np.nanmin(ci), np.nanmax(ci))
        write_to_file_field(csr_ol.file, mapindex_udiv.write_raster, 'tiff')
        if runtypelevel >= 3:
            logger.debug('plotting and saving thumbnail MAPINDEX-UDIV')
            plot_map(mapindex_udiv, csr_ol.thumbnail, logcolor=False, quantile_outliers=0.98)

        if compute_aggregate_stats:
            aggregated_layers['CEASCORE'] = ci

        #PRESENVSCEA heatmap
        logger.debug('saving HEATPREENVCEA')
        cl = CodedLabel.objects.get(code='HEATPREENVCEA')
        csr_o = csr.outputs.create(coded_label=cl)
        out_presenvs = module_cs.outputs['presenvs']
        pescore = []
        totscore = 0
        for (k, l) in out_presenvs.items():
            (p, e) = k.split('--')
            pescore.append({
                'p': p,
                'e': e,
                'pescore': float(np.nansum(l))
            })
            totscore += np.nansum(l)
        write_to_file_field(csr_o.file, lambda buf: json.dump(pescore, buf), 'json', is_text_file=True)
        logger.debug('saving HEATPREENVCEA2')
        if runtypelevel >= 3:
            ax = plot_heatmap(pescore, 'p', 'e', 'pescore', scale_measure=totscore / 100, fmt='.1f', fillval=0, cbar=False, figsize=[8, 10])
            ax.set_title('CEA score (%)')
            ax.set_xlabel('Pressures')
            ax.set_ylabel('Environmental receptors')
            plt.tight_layout()
            write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
            plt.clf()
            plt.close()

        if runtypelevel < 3:
            return csr.id

        # WEIGHTS
        logger.debug('saving WEIGHTS')
        cl = CodedLabel.objects.get(code='PRESSURE-WEIGHTS')
        csr_o = csr.outputs.create(coded_label=cl)
        filter_used_weights = module_cs.weights.usecode.isin(module_cs.layers.code)
        matrix = module_cs.weights[filter_used_weights]
        # remove pressures with all zeros in weights
        _df = matrix.pivot('precode', 'usecode', 'weight')
        non_empty_pressures_uses = _df.loc[(_df!=0).any(axis=1)].index
        filter_used_pressures = module_cs.weights.precode.isin(non_empty_pressures_uses)
        matrix = module_cs.weights[filter_used_weights & filter_used_pressures]
        matrix = matrix.to_dict('record')
        write_to_file_field(csr_o.file, lambda buf: json.dump(matrix, buf), 'json', is_text_file=True)
        ax = plot_heatmap(matrix, 'usecode', 'precode', 'weight',
                          # scale_measure=1852,# nm conversion
                          fillval=0,
                          figsize=[8, 8],
                          cmap='Blues',
                          cbar=False
                          )

        ax.set_title('Weights matrix')
        ax.set_xlabel('Human uses')
        ax.set_ylabel('Pressures')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        # DISTANCES
        logger.debug('saving DISTANCES')
        cl = CodedLabel.objects.get(code='DISTANCES')
        csr_o = csr.outputs.create(coded_label=cl)
        write_to_file_field(csr_o.file, lambda buf: json.dump(matrix, buf), 'json', is_text_file=True)
        ax = plot_heatmap(matrix, 'usecode', 'precode', 'distance',
                          scale_measure=1852,# nm conversion
                          fillval=0,
                          figsize=[8, 8],
                          cmap='Greens',
                          cbar=False
                          )

        ax.set_title('Distances matrix (nm)')
        ax.set_xlabel('Human uses')
        ax.set_ylabel('Pressures')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        # SENS
        logger.debug('saving SENS')
        cl = CodedLabel.objects.get(code='SENS')
        csr_o = csr.outputs.create(coded_label=cl)
        # matrix = module_cs.sensitivities.to_dict('record')
        filter_used_sens = module_cs.sensitivities.envcode.isin(module_cs.layers.code)
        matrix = module_cs.sensitivities[filter_used_sens]
        # remove pressures with all zeros in weights
        _df = matrix.pivot('precode', 'envcode', 'sensitivity')
        non_empty_pressures_envs = _df.loc[(_df!=0).any(axis=1)].index
        filter_used_pressures = module_cs.sensitivities.precode.isin(non_empty_pressures_envs)
        matrix = module_cs.sensitivities[filter_used_sens & filter_used_pressures]
        matrix = matrix.to_dict('record')
        write_to_file_field(csr_o.file, lambda buf: json.dump(matrix, buf), 'json', is_text_file=True)
        ax = plot_heatmap(matrix, 'precode', 'envcode', 'sensitivity',
                          # scale_measure=1852,# nm conversion
                          fillval=0,
                          figsize=[10, 12],
                          cmap='cubehelix_r',
                          cbar=False
                          )

        ax.set_title('Sensitivities matrix')
        ax.set_xlabel('Pressures')
        ax.set_ylabel('Environmental receptors')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        # CEASCORE histogram
        cl = CodedLabel.objects.get(code='HISTCEASCORE')
        csr_o = csr.outputs.create(coded_label=cl)
        data = ci.flatten()
        data = data[data.mask == False]
        n, bins, patches = plt.hist(data, bins=15)
        histdata = {'n': n.tolist(), 'bins': bins.tolist()}
        write_to_file_field(csr_o.file, lambda buf: json.dump(histdata, buf), 'json', is_text_file=True)

        ax = plt.gca()
        ax.set_ylabel('n. of cells')
        totscoreperc = data.shape[0] / 100
        y1, y2 = ax.get_ylim()
        x1, x2= ax.get_xlim()
        ax2 = ax.twinx()
        ax2.set_ylim(y1/totscoreperc, y2/totscoreperc)
        ax2.set_ylabel('% of cells')

        ax.set_xlabel('CEA score')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        # # PRESCORE barplot
        # cl = CodedLabel.objects.get(code='BARPRESCORE')
        # csr_o = csr.outputs.create(coded_label=cl)
        # out_pressures = module_cs.outputs['pressures']
        # _pscores = [{'p': k, 'pscore': float(np.nansum(l))} for (k, l) in out_pressures.items() if np.nansum(l)>0]
        # write_to_file_field(csr_o.file, lambda buf: json.dump(_pscores, buf), 'json', is_text_file=True)
        # pscores = pd.DataFrame(_pscores)
        
        # pscores.set_index('p', inplace=True)
        # ax = pscores.plot.bar(legend=False)
        # ax.set_xlabel('Pressures')
        # ax.set_ylabel('pressure score')
        # totscoreperc = pscores.pscore.sum()/100
        # y1, y2 = ax.get_ylim()
        # x1, x2= ax.get_xlim()
        # ax2 = ax.twinx()
        # ax2.set_ylim(y1/totscoreperc, y2/totscoreperc)
        # ax2.set_ylabel('% of the total pressure score')
            
        # plt.tight_layout()
        # write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        # plt.clf()
        # plt.close()

        #USEPRESCORE heatmap
        cl = CodedLabel.objects.get(code='HEATUSEPRESCORE')
        csr_o = csr.outputs.create(coded_label=cl)
        out_usepressures = module_cs.outputs['usepressures']
        _upscores = []
        totscore = 0
        for (k, l) in out_usepressures.items():
            (u, p) = k.split('--')
            if np.nansum(l) == 0:
                continue
            _upscores.append({
                'u': u,
                'p': p,
                'upscore': float(np.nansum(l))
            })
            totscore += np.nansum(l)
        write_to_file_field(csr_o.file, lambda buf: json.dump(_upscores, buf), 'json', is_text_file=True)
        ax = plot_heatmap(_upscores, 'u', 'p', 'upscore', scale_measure=totscore / 100, fmt='.1f', fillval=0, cbar=False, figsize=[8, 10])
        ax.set_title('Pressure scores (%)')
        ax.set_xlabel('Uses')
        ax.set_ylabel('Pressures')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()


        #HEATUSEENVCEA heatmap
        cl = CodedLabel.objects.get(code='HEATUSEENVCEA')
        csr_o = csr.outputs.create(coded_label=cl)
        out_usesenvs = module_cs.outputs['usesenvs']
        uescore = []
        totscore = 0
        for (k, l) in out_usesenvs.items():
            (u, e) = k.split('--')
            uescore.append({
                'u': u,
                'e': e,
                'uescore': float(np.nansum(l))
            })
            totscore += np.nansum(l)
        write_to_file_field(csr_o.file, lambda buf: json.dump(uescore, buf), 'json', is_text_file=True)
        ax = plot_heatmap(uescore, 'u', 'e', 'uescore', scale_measure=totscore / 100, fmt='.1f', fillval=0, cbar=False, figsize=[8, 10])
        ax.set_title('CEA score (%)')
        ax.set_xlabel('Human uses')
        ax.set_ylabel('Environmental receptors')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        ceamaxval = np.nanmax(ci)
        MSFDGROUPS = {'Biological': 'MAPCEA-MSFDBIO',
                      'Physical': 'MAPCEA-MSFDPHY',
                      'Substances, litter and energy': 'MAPCEA-MSFDSUB'}
        for ptheme, msfdcode in MSFDGROUPS.items():
            logger.debug('saving {}'.format(msfdcode))
            plist = list(Pressure.objects.filter(msfd__theme=ptheme).values_list('code', flat=True))
            module_cs.run(uses=uses, envs=envs, pressures=plist)
            #
            ci = module_cs.outputs['ci']
            cl = CodedLabel.objects.get(code=msfdcode)

            plist_str = ", ".join(CodedLabel.objects.filter(code__in=plist).values_list('label', flat=True))
            description = 'MSFD {} pressures: {}'.format(ptheme, plist_str)
            csr_ol = csr.outputlayers.create(coded_label=cl, description=description)
            write_to_file_field(csr_ol.file, ci.write_raster, 'tiff')
            logger.debug('plotting and saving thumbnail {}'.format(msfdcode))
            plot_map(ci, csr_ol.thumbnail, ceamaxval=ceamaxval, quantile_outliers=0.98)

            if compute_aggregate_stats:
                aggregated_layers[msfdcode] = ci
        # TODO: generalize step = 2
        if compute_aggregate_stats:
            for code, l in module_cs.layers.iterrows():
                aggregated_layers[code] = l.layer

            module_cs.outputs['aggregated_gdf'] = aggregate_layers_to_gdf(aggregated_layers, step=2, melt=True)

    elif csr.casestudy.module == 'muc':
        # csr.casestudy.set_or_update_context('CATALUNIA')
        module_cs.load_layers()
        module_cs.load_grid()
        module_cs.load_inputs()
        module_cs.run(uses=uses, pivot_layer=pivot_layer)
        totalscore = module_cs.outputs['muc_totalscore']

        # MUCSCORE map
        out = module_cs.outputs['muc']
        cl = CodedLabel.objects.get(code='MUCSCORE')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        write_to_file_field(csr_ol.file, out.write_raster, 'tiff')
        plt.figure(figsize=get_map_figure_size(out.bounds))
        ax, mapimg = out.plotmap(#ax=ax,
                   cmap='jet',
                   logcolor=True,
                   legend=True,
                   # maptype='minimal',
                   grid=True, gridrange=1)
        # ax.add_image(cimgt.Stamen('toner-lite'), get_zoomlevel(out.geobounds))
        # CEASCORE map as png for
        write_to_file_field(csr_ol.thumbnail, plt.savefig, 'png')
        plt.clf()

        # PCONFLICT
        cl = CodedLabel.objects.get(code='PCONFLICT')
        csr_o = csr.outputs.create(coded_label=cl)
        # pconflict = MUCPotentialConflict.objects.get_matrix('CATALUNIA')
        
        filter_used_columns = module_cs.potential_conflict_scores.columns.isin(module_cs.layers.code)
        filter_used_rows = module_cs.potential_conflict_scores.index.isin(module_cs.layers.code)
        matrix = module_cs.potential_conflict_scores.loc[filter_used_rows, filter_used_columns]
        filter_triu = np.triu(np.ones(matrix.shape), k=1).astype(np.bool)
        matrix = matrix.where(filter_triu)
        matrix = matrix.stack().reset_index(name='score')
        matrix = matrix.to_dict('record')
        
        write_to_file_field(csr_o.file, lambda buf: json.dump(matrix, buf), 'json', is_text_file=True)
        ax = plot_heatmap(matrix, 'u1', 'u2', 'score',
                          figsize=[12, 12],
                          sparse_tri=True,
                          fmt='.0f', fillval=0, cbar=False,
                          square=True)
        ax.set_title('Potential conflict')
        ax.set_xlabel('Use')
        ax.set_ylabel('Use')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()

        # HEATUSEMUC
        cl = CodedLabel.objects.get(code='HEATUSEMUC')
        csr_o = csr.outputs.create(coded_label=cl)
        out_muc_couses = module_cs.outputs['muc_couses']
        write_to_file_field(csr_o.file, lambda buf: json.dump(out_muc_couses, buf), 'json', is_text_file=True)
        ax = plot_heatmap(out_muc_couses, 'u1', 'u2', 'score',
                          # scale_measure=totscore/100,
                          figsize=[12, 12],
                          scale_measure=totalscore/100,
                          sparse_tri=True,
                          fmt='.1f', fillval=0, cbar=False,
                          square=True)
        ax.set_title('MUC scores (%)')
        ax.set_xlabel('Use')
        ax.set_ylabel('Use')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        return csr.id

    elif csr.casestudy.module == 'partrac':
        # module_cs.load_layers()
        module_cs.load_grid()
        module_cs.load_inputs()
        module_cs.run(scenario=1)
        time_rasters = module_cs.outputs['time_rasters']
        # collect statistics
        vmaxcum = np.asscalar(max([np.nanmax(r[1]) for r in time_rasters]))
        vmax = np.asscalar(max([np.nanmax(r[2]) for r in time_rasters]))

        CRS = cartopy.crs.Mercator()

        cropped = time_rasters[-1][1].copy()  # crop last cumraster
        cropped = cropped.crop(value=0)

        def update_frame(iternum, *fargs):
            rindex = fargs[0]
            ax = fargs[1]
            vmax = fargs[2]
            time_step = time_rasters[iternum][0]
            raster = time_rasters[iternum][rindex]
            raster = raster.to_srs_like(cropped)
            # raster[:] = 0
            raster.mask = raster <= 0.0001
            plt.title("Hours: {}".format(time_step))
            # remove legends
            legend = True
            im = ax.images
            if len(im) > 0:
                legend = False
            # else:
            #     ax.add_image(cimgt.Stamen('toner-lite'), get_zoomlevel(raster.geobounds))
            # print(iternum, rindex, raster.max(), vmax)
            raster.plotmap(ax=ax,
                           # etopo=True,
                           # zoomlevel=7,
                           grid=True,
                           vmax=vmax,
                           legend=legend,
                           cmap="jet",
                           logcolor=True)

        def write_to_buffer(buf, aniobj=None):
            tfn = tempfile.mktemp('.gif')
            # try:
            aniobj.save(tfn, dpi=120, writer='imagemagick')
            with open(tfn, "rb") as f:
                buf.write(f.read())
            # finally:
            #    os.remove(tfn)

        fig, ax = plt.subplots(figsize=[12, 12], subplot_kw={'projection': CRS})
        fig.set_tight_layout(True)

        ani = animation.FuncAnimation(fig, update_frame,
                                      frames=range(0, len(time_rasters)),
                                      interval=1000, blit=False,
                                      repeat_delay=4000, fargs=[1, ax, vmaxcum])

        cl = CodedLabel.objects.get(code='PARTRACSCORE')
        csr_o = csr.outputlayers.create(coded_label=cl, description="Diffusion from ontinuous source")
        # csr_o = csr.outputs.create(coded_label=cl, description="Diffusion from ontinuous source")

        write_to_file_field(csr_o.thumbnail, write_to_buffer, 'gif', aniobj=ani)
        plt.clf()

        write_to_file_field(csr_o.file, time_rasters[-1][1].copy().write_raster, 'tiff')

        fig, ax = plt.subplots(figsize=[12, 12], subplot_kw={'projection': CRS})
        fig.set_tight_layout(True)

        ani = animation.FuncAnimation(fig, update_frame,
                                      frames=range(0, len(time_rasters)),
                                      interval=1000, blit=False,
                                      repeat_delay=4000, fargs=[2, ax, vmax]) # use second raster (non-cumulative)

        csr_o = csr.outputlayers.create(coded_label=cl, description="Dispersion from impulsive source")
        # csr_o = csr.outputs.create(coded_label=cl, description="Dispersion from impulsive source")

        write_to_file_field(csr_o.thumbnail, write_to_buffer, 'gif', aniobj=ani)
        plt.clf()
        write_to_file_field(csr_o.file, time_rasters[-1][2].copy().write_raster, 'tiff')
        return csr.id

    elif csr.casestudy.module == 'pmar':
        module_cs.load_layers()
        module_cs.load_inputs()
        module_cs.layer_preprocessing()
        df_domain_area = None
        if csr.casestudy.domain_area is not None:
            domain_area = csr.casestudy.domain_area
            if domain_area.geom_type == 'MultiPolygon':
                areas = {i: da.area for i, da in enumerate(domain_area)}
                domain_area = domain_area[max(areas, key=areas.get)]
                
            #     df_domain_area = csr.casestudy.domain_area_to_gdf()
            # else:
            #     message = 'The domain_area is not a Polygon. It cannot be used for seeding'
            #     logger.warning(message)
            #     print(message)
                
        module_cs.run(selected_layers=selected_layers, df_domain_area=_domain_area_to_gdf(domain_area), runtypelevel=runtypelevel, context=csr.casestudy.default_context.label)
        # pmar_result = module_cs.outputs['pmar_result']
        # print("################")
        # print(pmar_result)
        # cl = CodedLabel.objects.get(code='PMAR-RESULTS')
        # csr_o = csr.outputs.create(coded_label=cl)
        # write_to_file_field(csr_o.file, lambda buf: json.dump(pmar_result, buf), 'json', is_text_file=True)

        for c, layer in module_cs.outputs['pmar_result_layers'].items():
            cl = CodedLabel.objects.get(code=c)
            csr_ol = csr.outputlayers.create(coded_label=cl)
            # print(np.nanmin(ci), np.nanmax(ci))
            write_to_file_field(csr_ol.file, layer['output'].write_raster, 'tiff')
            write_to_file_field(csr_ol.thumbnail, layer['thumbnail'].save, 'png', format='PNG')
            # plot_map(layer, csr_ol.thumbnail)

    elif csr.casestudy.module == 'geodatamaker':
        module_cs.load_layers()
        module_cs.load_inputs()
        module_cs.layer_preprocessing()
        module_cs.run(selected_layers=selected_layers, runtypelevel=runtypelevel)
        for c, layer in module_cs.outputs['layers'].iterrows():
            cl = CodedLabel.objects.get(code=c)
            csr_ol = csr.outputlayers.create(coded_label=cl)
            # print(np.nanmin(ci), np.nanmax(ci))
            write_to_file_field(csr_ol.file, layer['layer'].write_raster, 'tiff')
            plot_map(layer['layer'], csr_ol.thumbnail)
            # def save_shp_wrapper(buf):
            #     with tempfile.TemporaryDirectory() as tmpdirname:
            #         gdf = module_cs.outputs['aggregated_gdf']
            #         gdf.to_file(tempdirname.name, driver='ESRI Shapefile')
            #         with tempfile.NamedTemporaryFile(suffix=".shp") as fp:
            #             archiveFile = shutil.make_archive(fp.name, 'zip', tempdirname.name)
            #             zip = open(archiveFile, 'rb')
            #             buf.write(fzip.read())

            # write_to_file_field(csr_o.file, , 'shp.zip')

            # write_to_file_field(csr_ol.thumbnail, layer['thumbnail'].save, 'png', format='PNG')
            # plot_map(layer, csr_ol.thumbnail)

        # related = []
        # # get outputlayers
        # for f in csr.casestudy._meta.get_fields():
        #     if f.one_to_many and f.field.model==CaseStudyLayer:
        #         related_name = f.get_accessor_name()
        #         related.extend(getattr(csr.casestudy, related_name).all())

        # # copy input layers to outputlayers
        # for o in related:
        #     csr_o = csr.outputlayers.create(coded_label=o.coded_label)
        #     if bool(o.file):
        #         new_file = ContentFile(o.file.read())
        #         new_file.name = o.file.name
        #         csr_o.file = new_file

        #     if bool(o.thumbnail):
        #         new_file = ContentFile(o.thumbnail.read())
        #         new_file.name = o.thumbnail.name
        #         csr_o.thumbnail = new_file
        #     csr_o.save()

        
    elif csr.casestudy.module == 'testmodule':
        module_cs.run()
        testmodule_result = module_cs.outputs['testmodule_result']
        print("################")
        print(testmodule_result)
        cl = CodedLabel.objects.get(code='TESTMODULERES')
        csr_o = csr.outputs.create(coded_label=cl)
        write_to_file_field(csr_o.file, lambda buf: json.dump(testmodule_result, buf), 'json', is_text_file=True)


        #
        # fig, axs = plt.subplots(3, 3, figsize=(15, 20),
        #                         subplot_kw={'projection': CRS})
        # axs = axs.ravel()
        #
        # cropped = time_rasters[-1][1].copy()  # crop last cumraster
        # cropped = cropped.crop(value=0)
        # for i, (timeid, raster) in enumerate(time_rasters):
        #     ax = axs[i]
        #     raster = raster.to_srs_like(cropped)
        #     raster.mask = raster == 0
        #     raster.plotmap(ax=ax, etopo=True, zoomlevel=6)
        #     ax.set_title('Time: {}'.format(timeid))
        #     # ax.add_geometries([INPUT_GEO_3857.buffer(BUFFER)], crs=CRS,
        #     #                   facecolor="None",
        #     #                   edgecolor='black',
        #     #                   linewidth=4,
        #     #                   # alpha=0.4,
        #     #                   zorder=4)
        # cl = CodedLabel.objects.get(code='HEATUSEMUC')
        # csr_o = csr.outputs.create(coded_label=cl)
        # plt.tight_layout()
        # write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        # plt.clf()
        #
        # return module_cs
    else:
        return None


    # if the outputs contain a aggregated_gdf key, a shpfile will be
    # save as csr output
    if 'aggregated_gdf' in module_cs.outputs:
        cl = CodedLabel.objects.get(code="SHP-AGGREGATE-STATS")
        csr_o = csr.outputs.create(coded_label=cl)
        write_empty_file_field(csr_o.file, 'shp.zip')
        gdf = module_cs.outputs['aggregated_gdf']
        if 'group' not in gdf.columns:
            code_groups = {code: group for code, group in CodedLabel.objects.all().order_by('group', 'code').values_list('code', 'group')}
            gdf['group'] = gdf.variable.replace(code_groups)
        with tempfile.TemporaryDirectory() as tempdirname:
            gdf.to_file(tempdirname, driver='ESRI Shapefile')
            #override just create file. We have to removed the last 4 char (.zip suffix)
            archiveFile = shutil.make_archive(csr_o.file.path[:-4], 'zip', tempdirname)
            print(archiveFile)
            
    del module_cs
    return csr.id


def check_coded_labels(selected_layers):
    uses = None
    envs = None
    pres = None
    usespres = None
    if selected_layers is not None:
        coded_labels = CodedLabel.objects.get_dict()
        uses = []
        envs = []
        pres = []
        for code in selected_layers:
            l = coded_labels.get(code, {})
            g = l.get('group', None)
            if g == 'use':
                uses.append(code)
            elif g == 'env':
                envs.append(code)
            elif g == 'pre':
                pres.append(code)
            elif g == 'usepre':
                _use, _pre = code.split('--')
                uses.append(_use)
                # WARNING: pressure from usepre is not included
                # TODO: make more robust
                # pres.append(_pre)
        if len(uses) == 0:
            uses = None
        if len(envs) == 0:
            envs = None
        if len(pres) == 0:
            pres = None
    return uses, pres, envs

def _domain_area_to_gdf(domain_area):
    feature = wkt.loads(domain_area.wkt)
    # TODO: there is a problem on lat, lon order
    # revert lat, lon order
    _feature = transform(lambda x, y: (y, x), feature)
    gdf = gpd.GeoDataFrame([{'geometry': _feature}], geometry='geometry', crs='epsg:4326')
    return gdf
    
def _guess_ncells(domain_area, resolution):
    gdf = _domain_area_to_gdf(domain_area)
    bounds = gdf.to_crs(epsg=3035).total_bounds
    ncells = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / resolution / resolution
    return int(ncells)


class CaseStudy(models.Model):
    # id = models.AutoField(primary_key=True, help_text="AAAAAAAAA") # TODO: to be removed
    label = models.CharField(max_length=100, help_text="CaseStudy title")
    description = models.CharField(max_length=800, null=True, blank=True, help_text="CaseStudy description")

    cstype = models.CharField(_('CS Type'), max_length=10, choices=CASESTUDY_TYPE_CHOICES,
                              help_text="CaseStudy type. Accepted values are: {}".format(", ".join([t[0] for t in CASESTUDY_TYPE_CHOICES])))
    module = models.CharField(_('Module type'), max_length=15, choices=MODULE_TYPE_CHOICES,
                              help_text="Module type. Accepted values are: {}".format(
                                  ", ".join([t[0] for t in MODULE_TYPE_CHOICES])))
    tag = models.CharField(max_length=100, null=True, blank=True,
                           help_text="Free tag, label or keyword to facilitate CaseStudy identification and search")
    resolution = models.FloatField(default=1000, help_text='Default resolution for raster based analysis (meters)')
    domain_area = models.MultiPolygonField(blank=True, null=True,
                                           help_text="GeoJSON rapresentation of the CaseStudy domain area (MultiPolygon Lat Log WGS84)")
    domain_area_terms = models.ManyToManyField("DomainArea",
                                               blank=True,
                                               help_text="Domain area term. See DomainAreas thesaurus"
                                               )

    # tools4msp = models.BooleanField(_("Tools4MSP Case Study"), default=False,
    #                                 help_text=_('Is this a Tools4MSP Case Study?'))

    # reference to source dataset/layer
    domain_area_dataset = models.ForeignKey("CaseStudyGrid",
                                            blank=True,
                                            null=True,
                                            verbose_name="Domain area (source dataset)",
                                            on_delete=models.CASCADE)

    # grid_dataset = models.ForeignKey("Dataset", blank=True, null=True,
    #                                  verbose_name="Area of analysis")

    # grid_output = models.ForeignKey("Dataset", blank=True, null=True,
    #                                 related_name="casestudy_output",
    #                                 verbose_name="")
    # tool_coexist = models.BooleanField()
    # tool_ci = models.BooleanField()
    # tool_mes = models.BooleanField()

    is_published = models.BooleanField(_("Is Published"), default=False,
                                       help_text=_('Should this Case Study be published?'))

    visibility = models.IntegerField(default=0, choices=VISIBILITY_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    owner = models.ForeignKey('auth.User',
                              on_delete=models.CASCADE)

    client_application = models.ForeignKey(ClientApplication,
                                           on_delete=models.SET_NULL,
                                           null=True,
                                           blank=True)

    default_context = models.ForeignKey(Context, on_delete=models.CASCADE, blank=True, null=True)
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)

    # this has been removed in Django 2.2
    # objects = models.GeoManager()

    output_layer_model_config = None
    _output_layer_model = None

    # deprecated
    CS = None
    _module_cs = None

    def get_thumbnails(self):
        return CaseStudyInput.objects.filter(casestudy=self,
                                             coded_label__code="CS-THUMB")

    def set_domain_area(self):
        if self.domain_area_terms.count() > 0:
            geounion = self.domain_area_terms.aggregate(models.Union('geo'))['geo__union']
            extent = geounion.extent
            dlon = extent[2] - extent[0]
            dlat = extent[3] - extent[1]
            tolerance = min(dlon / 500, dlat/500, 0.01)
            geounion = geounion.simplify(tolerance)
            if geounion.geom_type != 'MultiPolygon':
                geounion = MultiPolygon(geounion)
            self.domain_area = geounion
            self.set_update_grid()

    def domain_area_to_gdf(self):
        return _domain_area_to_gdf(self.domain_area)

    def guess_ncells(self):
        return _guess_ncells(self.domain_area, self.resolution)
    
    def set_update_grid(self):
        if self.domain_area is None:
            return None
        else:
            gdf = self.domain_area_to_gdf()
            l = rg.read_df(gdf, self.resolution, epsg=3035, eea=True)
            l.mask = l==0
            code = 'GRID'
            cl = CodedLabel.objects.get(code=code)
            # this override previous results
            csr_ol, created = self.layers.get_or_create(coded_label=cl)
            csr_ol.file = None
            csr_ol.thumbnail = None
            csr_ol.save()
            write_to_file_field(csr_ol.file, l.write_raster, 'tiff')
            plot_map(l, csr_ol.thumbnail, ceamaxval=None, logcolor=False)

    def set_layer_weights(self, cl_sorter=None):
        self.set_or_update_input('LAYER-WEIGHTS', self.default_context, cl_sorter=cl_sorter)

    def set_or_update_input(self, coded_label, context_label, vizmode=1, cl_sorter=None, overwrite=False):
        cl = CodedLabel.objects.get(code=coded_label)
        layers_info =  {d['layer']: "sum={sumval:.2f}, min={minval:.2f}, max={maxval:.2f} mean={meanval:.2f}".format(**json.loads(d['layerinfo'])) for d in self.layers.all().values('layerinfo', layer=F('coded_label__code'))}
        layers_list = list(layers_info.keys())
        ## append usepre
        codedlabels_list = layers_list
        for ll in layers_list:
            if '--' in ll:
                codedlabels_list = codedlabels_list + ll.split('--')

        layers_list = [{'layer': code} for code in set(layers_list)]
        codedlabels_list = [{'layer': code} for code in set(codedlabels_list)] 

        module_cs = self.module_cs
        df1 = module_cs.load_input(cl.filename_prefix)

        def _merge(_df1, _df2, ucols=None):
            if _df1 is not None:
                df = pd.concat([_df1, _df2])
            else:
                df = _df2

            if ucols is not None:
                keep = 'first' if not overwrite else 'last'
                df = df.drop_duplicates(ucols, keep=keep)
            return df

        logger.debug(coded_label)
        logger.debug(context_label)
        logger.debug("DFA1")
        # logger.debug(df1.to_json(orient='records'))
        
        cols_to_sort = None
        if coded_label=='WEIGHTS': # deprecated
            df2 = pd.DataFrame(Weight.objects.get_matrix(context_label))
            ucols = ['u', 'p']
            layer_col = 'u'
        if coded_label=='PRESSURE-WEIGHTS':
            df2 = pd.DataFrame(Weight.objects.get_matrix(context_label))
            df2.rename(columns={'use_code': 'use', 'pressure_code': 'pressure'}, inplace=True)
            # df2.loc[df2.weight>0,'weight'] = 100
            ucols = ['use', 'pressure']
            layer_col = 'use'
            cols_to_sort = ucols
        elif coded_label=='LAYER-WEIGHTS':
            _type = "select"
            rescale_options = [
                ['none', 'None'],
                ['rescale', 'Rescale (max=1)'],
                ['log', 'Log'],
                ['logrescale', 'Log and rescale (max=1)'],
                ['normlog', '100-Normalized log'],
                ['normlogrescale', '100-Normalized log and rescale (max=1)'],
                ['pa', 'Presence-absence (0-1)'],
                
            ]
            df2_1 = pd.DataFrame([dict(item, weight='none', param="RESCALE-MODE", _type=_type, _options=rescale_options) for item in layers_list])
            df2_2 = pd.DataFrame([dict(item, weight=1, param="WEIGHT-FREQUENCY", _type="number", _options=None) for item in layers_list])
            df2_3 = pd.DataFrame([dict(item, weight=1, param="WEIGHT-MAGNITUDE", _type="number", _options=None) for item in layers_list])
            df2_4 = pd.DataFrame([dict(item, weight=1, param="WEIGHT-RELEVANCE", _type="number", _options=None) for item in layers_list])
            # init layer-info as empty string
            df2_5 = pd.DataFrame([dict(item, weight='', param="LAYER-INFO", _type="select", _options=None) for item in layers_list])

            df2 = pd.concat([df2_1, df2_2, df2_3, df2_4, df2_5], axis=0)
            # print(df2)
            # print(pd.concat
            ucols = ['layer', 'param']
            layer_col = 'layer'
            # cols_to_sort = ['layer', 'param']
            cols_to_sort = ['layer', 'param']
        elif coded_label=='SENSITIVITIES':
            df2 = pd.DataFrame(Sensitivity.objects.get_matrix(context_label))
            df2.rename(columns={'env_code': 'env', 'pressure_code': 'pressure'}, inplace=True)

            ucols = ['env', 'pressure']
            layer_col = 'env'
            cols_to_sort = ucols

        # logger.debug("DFA2")
        # logger.debug(df2.to_json(orient='records'))

        df = _merge(df1, df2, ucols)
        if layer_col is not None and df.shape[0] > 0:
            # logger.debug(df.to_json(orient='records'))
            df = df[df[layer_col].isin([r['layer'] for r in codedlabels_list])] 
        # logger.debug("dentre")
        # logger.debug(df2.to_json(orient='records'))


        # fill gaps
        if coded_label=='WEIGHTS': # deprecated
            df = df.pivot(index='u', columns='p').fillna(0).stack().reset_index()
        elif coded_label=='LAYER-WEIGHTS':
            # rescale_options is a dictionary, so I need to apply it to every element
            _filter = df.param=='RESCALE-MODE'
            df.loc[_filter, '_options'] = df[_filter]._options.apply(lambda x: rescale_options)

            # layer-info is always updated
            _filter = df.param=='LAYER-INFO'
            df.loc[_filter, 'weight'] = df[_filter].layer.replace(layers_info)
            df.loc[_filter, '_options'] = df[_filter].weight.apply(lambda x: [['info', x]])
                        
            print(df.loc[_filter, '_options'])
        elif coded_label=='PRESSURE-WEIGHTS':
            # logger.debug("kaput")
            # logger.debug(df.columns)
            # logger.debug(df.index)
            df = df.pivot(index='use', columns='pressure').fillna(0).stack().reset_index()
        elif coded_label=='SENSITIVITIES':
            # df = df.pivot(index='pressure', columns='env').fillna(0).stack().reset_index()
            df = df.pivot(index='pressure', columns='env').fillna(0).stack().reset_index()
            if df.shape[0] > 0:
                df.loc[df.impact_level==0, 'impact_level'] = 0.01
                df.loc[df.recovery_time==0, 'recovery_time'] = 0.01
                df.loc[df.confidence==0, 'confidence'] = 0.
                df.loc[df.sensitivity==0, 'sensitivity'] = 0.01 * 0.01

        logger.debug(cols_to_sort)
        if cl_sorter is not None and cols_to_sort is not None:
            logger.error("dentro, dentro")
            for c in cols_to_sort:
                df[c] = df[c].astype('category')
                df[c].cat.set_categories(cl_sorter)
            df.sort_values(cols_to_sort, inplace=True)

        csi, created = self.inputs.get_or_create(coded_label=cl, defaults={'vizmode': vizmode, 'description': cl.description})
        jsonstring = df.to_json(orient='records')
        #WARNING: this remove None or nodata values from the json export
        # jsonstring = df.apply(lambda x: x.dropna().to_dict(), axis=1).to_json(orient="records")
        # only the file extension matters
        csi.file.save('file.json', File(StringIO(jsonstring)))
        # print(jsonstring)
        return df
        
        
    def set_or_update_context2(self, context_label):
        self.default_context = Context.objects.get(label=context_label)
        self.save()
        
    
    def set_or_update_context(self, context_label=None, overwrite=False):
        if context_label is not None:
            self.default_context = Context.objects.get(label=context_label)
            self.save()
        else:
            context_label = self.default_context.label
        cl_sorter = list(CodedLabel.objects.all().order_by('group', 'code').values_list('code', flat=True)) 
        # TODO: this is a module-aware function. Move to the module library
        if self.module == 'cea':
            # weights
            # cl = CodedLabel.objects.get(code='WEIGHTS')
            # csi, created = self.inputs.get_or_create(coded_label=cl)
            # s = Weight.objects.get_matrix(context_label)
            # jsonstring = json.dumps(s)
            # only the file extension matters
            # csi.file.save('file.json', File(StringIO(jsonstring)))
            self.set_layer_weights(cl_sorter=cl_sorter)
            self.set_or_update_input('PRESSURE-WEIGHTS', context_label, cl_sorter=cl_sorter, overwrite=overwrite)
            

        if self.module == 'cea':
            # set sensitivity
            # cl = CodedLabel.objects.get(code='SENS')
            # csi, created = self.inputs.get_or_create(coded_label=cl)
            # s = Sensitivity.objects.get_matrix(context_label)
            # jsonstring = json.dumps(s)
            # only the file extension matters
            # csi.file.save('file.json', File(StringIO(jsonstring)))
            self.set_or_update_input('SENSITIVITIES', context_label, cl_sorter=cl_sorter, overwrite=overwrite)

        if self.module == 'muc':
            # muc potential conflict matrix
            cl = CodedLabel.objects.get(code='PCONFLICT')
            csi, created = self.inputs.get_or_create(coded_label=cl)
            s = MUCPotentialConflict.objects.get_matrix(context_label)
            jsonstring = json.dumps(s)
            # only the file extension matters
            csi.file.save('file.json', File(StringIO(jsonstring)))

        if self.module == 'pmar':
            self.set_layer_weights(cl_sorter=cl_sorter)
            from tools4msp.modules.pmar import PMARPARAMS
            cl = CodedLabel.objects.get(code='PMAR-CONF')
            csi, created = self.inputs.get_or_create(coded_label=cl, defaults={'vizmode': 1}, description=cl.description)
            jsonstring = json.dumps(PMARPARAMS)
            # only the file extension matters
            csi.file.save('file.json', File(StringIO(jsonstring)))

        if self.module == 'testmodule':
            from tools4msp.modules.testmodule import TESTPARAMS
            cl = CodedLabel.objects.get(code='TESTPARAMS')
            csi, created = self.inputs.get_or_create(coded_label=cl, defaults={'vizmode': 1})
            jsonstring = json.dumps(TESTPARAMS)
            # only the file extension matters
            csi.file.save('file.json', File(StringIO(jsonstring)))

    def save(self, *args, **kwargs):
        # self.set_domain_area()
        super().save(*args, **kwargs)
        # self.domain_area_terms.clear()

    def __str__(self):
        return self.label

    class Meta:
        verbose_name_plural = "Case studies"
        permissions = (
            # New Django version already support view permission
            # ('view_casestudy', 'View case study'),
            ('download_casestudy', 'Download case study'),
            ('run_casestudy', 'Run case study'),
        )
        ordering = ['-cstype', 'created']


    # TODO: add deprecated warning
    def get_CS(self):
        if self.CS is not None:
            return self.CS
        version = 'v1'
        rtype = 'full'
        self.CS = CS(None,
                     basedir=TOOLS4MSP_BASEDIR,
                     name=str(self.id),
                     version=version,
                     rtype=rtype)

        return self.CS

    @property
    def module_cs(self):
        module_class = None
        if self._module_cs is not None:
            return self._module_cs
        if self.module == 'cea':
            module_class = CEACaseStudy
        elif self.module == 'muc':
            module_class = MUCCaseStudy
        elif self.module == 'partrac':
            module_class = ParTracCaseStudy
        elif self.module == 'pmar':
            module_class = PMARCaseStudy
        elif self.module == 'testmodule':
            module_class = TESTCaseStudy
        elif self.module == 'geodatamaker':
            module_class = GeoDataMakerCaseStudy

        if module_class is not None:
            self._module_cs = module_class(csdir=self.csdir)
        return self._module_cs

    @property
    def csdir(self):
        return path.join(settings.MEDIA_ROOT,
                         'casestudy',
                          str(self.pk))

    def sync_CS(self):
        cs = self.get_CS()
        cs.grid = self.get_grid()
        self.sync_datasets(grid=cs.grid.copy())
        self.sync_coexist_scores()
        self.sync_weights()
        self.sync_sensitivities()
        self.sync_pres_sensitivities()
        cs.dump_inputs()

    def sync_datasets(self, grid):
        cs = self.get_CS()
        # cs.load_layers()
        for d in self.casestudyuse_set.all():
            d.update_dataset('use', grid=grid)
        for d in self.casestudyenv_set.all():
            d.update_dataset('env', grid=grid)
        for d in self.casestudypressure_set.all():
            d.update_dataset('pre', grid=grid)
        cs.dump_layers()

    def _get_combs(self):
        uses = list(self.casestudyuse_set.values_list('name__pk', flat=True))
        # TODO: togliere cablatura U94
        uses.append(94)

        envs = self.casestudyenv_set.values_list('name__pk', flat=True)
        combs = list(itertools.product(uses, envs))
        return combs

    def get_pressures_list(self):
        pressures = []
        combs = self._get_combs()
        for p in combs:
            use = p[0]
            env = p[1]
            # TODO: migrare verso la nuova struttura
            # quando saranno migrate le sensitivities
            sens = get_sensitivities_by_rule(use, env)

            for s in sens:
                if s.pressure not in pressures:
                    pressures.append(s.pressure)
        # adding direct pressures
        pres_layers = self.casestudypressure_set.all()
        for pres_layer in pres_layers:
            if pres_layer.name.pk not in [p.id for p in pressures]:
                pressures.append(pres_layer.name)

        return pressures

    # new structure
    def sync_weights(self):
        cs = self.get_CS()
        if not hasattr(cs, 'weights'):
            return False
        cs.weights = cs.weights[0:0]  # empty

        up = self.casestudypressure_set.filter(source_use__isnull=False)
        uses = set(up.values_list('source_use', flat=True))
        uses |= set(self.casestudyuse_set.values_list('name', flat=True))
        for uid in uses:
            use = Use.objects.get(pk=uid)
            for w in Weight.objects.filter(use=use):
                cs.add_weights(
                    'u{}'.format(uid),
                    use.label,
                    'p{}'.format(w.pressure.id),
                    w.pressure.label,
                    w.weight, w.distance)
    #
    def sync_pres_sensitivities(self):
        cs = self.get_CS()
        if not hasattr(cs, 'pres_sensitivities'):
            return False
        cs.pres_sensitivities = cs.pres_sensitivities[0:0]  # empty
        envs = self.casestudyenv_set.all()
        for cenv in envs:
            env = cenv.name
            for s in Sensitivity.objects.filter(env=env):
                cs.add_pres_sensitivities(
                    'p{}'.format(s.pressure.id),
                    s.pressure.label,
                    'e{}'.format(s.env.id),
                    s.env.label,
                    s.sensitivity)

    # old structure
    def sync_sensitivities(self):
        cs = self.get_CS()
        combs = self._get_combs()

        cs.sensitivities = cs.sensitivities[0:0]  # empty
        for p in combs:
            use = p[0]
            env = p[1]
            # TODO: migrare verso la nuova struttura
            # quando saranno migrate le sensitivities
            sens = get_sensitivities_by_rule(use, env)

            for s in sens:
                distance = s.distance
                cs.add_sensitivity(
                    'u{}'.format(use),
                    s.activity_and_use.label,
                    'e{}'.format(env),
                    s.evironmental_component.label,
                    'p{}'.format(s.pressure.id),
                    s.pressure.label,
                    s.total_score, distance, s.confidence
                )

    def sync_coexist_scores(self):
        cs = self.get_CS()

        uses = list(self.casestudyuse_set.values_list('name__pk', flat=True))

        for use1, use2 in itertools.combinations(uses, 2):
            score = get_conflict_by_uses(use1, use2)
            if use1 != use2:
                u1 = Use.objects.get(pk=use1)
                u2 = Use.objects.get(pk=use2)
                cs.add_coexist_score("u{}".format(u1.pk), u1.label,
                                     "u{}".format(u2.pk), u2.label,
                                     score=score)
        # custom rules
        # TODO: rendere configurabili da interfaccia
        cs.coexist_scores.loc['u92',:] = 0 # reset no trawling area
        cs.coexist_scores.loc[:,'u92'] = 0 # reset no trawling area
        cs.add_coexist_score('u92', None, 'u86', None, score=5)
        cs.add_coexist_score('u92', None, 'u85', None, score=5)
        cs.add_coexist_score('u89', None, 'u85', None, score=2)
        cs.add_coexist_score('u89', None, 'u86', None, score=2)
        cs.add_coexist_score('u89', None, 'u75', None, score=2)
        cs.add_coexist_score('u89', None, 'u87', None, score=2)

        # MPA and aquaculture
        cs.add_coexist_score('u91', None, 'u84', None, score=0)

    def get_grid(self):
        module_cs = self.module_cs
        if module_cs is not None:
            return self.module_cs.get_grid()
        return None

    def gridinfo(self):
        try:
            gridinfo = self.layers.get(coded_label__code='GRID').layerinfo
            return gridinfo
        except ObjectDoesNotExist:
            return None

    def get_thumbnail_url(self):
        l = self.domain_area_dataset.get_layers_qs()[0]
        return l.thumbnail_url

    @property
    def thumbnail_url(self):
        return self.get_thumbnail_url()

    @mark_safe
    def thumbnail_tag(self):
        if self.thumbnail_url is not None:
            return '<img src="{}" width="200"/>'.format(self.thumbnail_url)
        else:
            return ''
    thumbnail_tag.short_description = 'Thumbnail'

    def run(self, selected_layers=None, runtypelevel=3, pivot_layer=None):
        # if self.pk == 66:
        #     rlist = self.casestudyrun_set.filter(pk=2963)
        # if False: #self.module in ['cea', 'muc', 'partrac']:
        # if self.module in ['cea', 'muc', 'partrac']:
        if self.module in ['cea', 'muc']:
            conf = {'selected_layers': selected_layers,
                    'runtypelevel': runtypelevel,
                    'pivot_layer': pivot_layer}
            csr = self.casestudyrun_set.create(configuration=conf)

            _run(csr, runtypelevel=runtypelevel)
            rlist = self.casestudyrun_set.filter(pk=csr.pk)
        else:
            import time
            time.sleep(5)
            rlist = self.casestudyrun_set.all().order_by('-id')
        if rlist.count() > 0:
            return rlist[0]
        return None

    def asyncrun(self, selected_layers=None, runtypelevel=3, owner=None, domain_area=None):
        # if self.pk == 66:
        #     rlist = self.casestudyrun_set.filter(pk=2963)
        # if False: #self.module in ['cea', 'muc', 'partrac']:
        # if self.module in ['cea', 'muc', 'partrac']:
        if self.module in ['cea', 'muc', 'pmar', 'geodatamaker', 'testmodule']:
            conf = {'selected_layers': selected_layers,
                    'runtypelevel': runtypelevel}
            uses, pres, envs = check_coded_labels(selected_layers)

            uses_desc = 'All'
            if uses is not None:
                uses_desc = ', '.join(uses)
            envs_desc = 'All'
            if envs is not None:
                envs_desc = ', '.join(envs)
            description = "Uses: {}. Receptors: {}".format(uses_desc, envs_desc)
            csr = self.casestudyrun_set.create(configuration=conf, owner=owner, description=description)

            # create outputgrid
            if domain_area is not None:
                i = self.domain_area.intersection(domain_area)
                if isinstance(i, Polygon):
                    i = MultiPolygon(i)
                csr.domain_area = i
                csr.set_update_outputgrid()

            async_task(run_wrapper, csr.pk, runtypelevel, hook="tools4msp.hooks.set_runstatus")
            rlist = self.casestudyrun_set.filter(pk=csr.pk)
        else:
            import time
            time.sleep(5)
            rlist = self.casestudyrun_set.all().order_by('-id')
        if rlist.count() > 0:
            return rlist[0]
        return None

    def clone(self):
        # load as a new object to avoid conflict with "self"
        cs = CaseStudy.objects.get(pk=self.pk)

        clone_related = [CaseStudyLayer, CaseStudyInput]
        # collect related objects
        related = []
        for f in cs._meta.get_fields():
            if f.one_to_many and f.field.model in clone_related:
                related_name = f.get_accessor_name()
                related.extend(getattr(cs, related_name).all())

        # clone Case Study
        cs.pk = None
        cs.save()

        # clone related objects
        for o in related:
            o.pk = None
            o.casestudy = cs
            if bool(o.file):
                new_file = ContentFile(o.file.read())
                new_file.name = o.file.name
                o.file = new_file

            if bool(o.thumbnail):
                new_file = ContentFile(o.thumbnail.read())
                new_file.name = o.thumbnail.name
                o.thumbnail = new_file
            o.save()
        return cs


# def generate_filename(self, filename):
def generate_input_filename(self, filename):
    pass

def generate_output_filename(self, filename):
    pass

def generate_output_layer_filename(self, filename):
    pass

def generate_run_layer_filename(self, filename):
    pass

def generate_run_input_filename(self, filename):
    pass

def generate_run_output_filename(self, filename):
    pass

def generate_run_output_layer_filename(self, filename):
    pass

def generate_layer_filename(self, filename):
    pass

def generate_filename(self, filename):
    # TODO: add control to avoid file overwriting when more than one inline have the same coded_label
    parent_dir = None
    parent_id = None
    file_type = None
    _filename, suffix = path.splitext(filename)
    name = self.coded_label.filename_prefix
    if isinstance(self, (CaseStudyRunInput,
                         CaseStudyRunLayer,
                         CaseStudyRunOutput,
                         CaseStudyRunOutputLayer)):
        parent_dir = "casestudyruns"
        parent_id = self.casestudyrun.id
    else:
        parent_dir = "casestudy"
        parent_id = self.casestudy.id

    if isinstance(self, (CaseStudyLayer,
                         CaseStudyRunLayer)
                         ):
        file_type = 'layers'
        # suffix = 'geotiff'
    elif isinstance(self, CaseStudyRunOutputLayer):
        file_type = 'outputlayers'
        # suffix = 'geotiff'
    elif isinstance(self, (CaseStudyRunInput, CaseStudyInput)):
        file_type = 'inputs'
        # suffix = 'json'
    elif isinstance(self, CaseStudyRunOutput):
        file_type = 'outputs'
        # suffix = 'json'

    url = "{}/{}/{}/{}{}".format(parent_dir,
                                  parent_id,
                                  file_type,
                                  name,
                                  suffix
                                  )
    return url


class FileBase(models.Model):
    "Model for layer description and storage"
    coded_label = models.ForeignKey("CodedLabel", limit_choices_to={'group__in': ['casestudy',
                                                                                  'pre',
                                                                                  'usepre',
                                                                                  'env',
                                                                                  'use',
                                                                                  'out',
                                                                                  'cea',
                                                                                  'muc',
                                                                                  'partrac',
                                                                                  'pmar',
                                                                                  'testmodule']},
                                   on_delete=models.CASCADE)
    description = models.CharField(max_length=800, null=True, blank=True)
    file = models.FileField(blank=True,
                            null=True,
                            upload_to=generate_filename)
    thumbnail = models.ImageField(blank=True,
                            null=True,
                            # default="defaults/cs_thumb_default.png",
                            upload_to=generate_filename)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class LayerInfoMixin(FileBase):
    layerinfo = JSONField(null=True, blank=True)

    @property
    def layerinfo_str(self):
        if self.layerinfo is None:
            return None
        else:
            layer_info =  "min={minval:.2f}, max={maxval:.2f} mean={meanval:.2f} sum={sumval:.2f}".format(**self.layerinfo)
        return layer_info

        
    def save(self, *args, **kwargs):
        if self.coded_label is not None:
            try:
                self.layerinfo = get_layerinfo(self.file.path)
            except ValueError:
                pass
        super().save(*args, **kwargs)

    class Meta:
        abstract = True

## TODO: add constrain to avoid multiple CaseStudyLayer with the same coded_label
class CaseStudyLayer(LayerInfoMixin):
    "Model for layer description and storage"
    casestudy = models.ForeignKey(CaseStudy,
                                  on_delete=models.CASCADE,
                                  related_name="layers")

    def set_thumbnail(self, ceamaxval=None, logcolor=False):
        l = rg.read_raster(self.file.path)
        plot_map(l, self.thumbnail, ceamaxval=ceamaxval, logcolor=logcolor, coast=True, cmap="viridis", grid=False, alpha=0.75)

    def mask_layer_with_grid(self):
        grid = self.casestudy.get_grid()
        raster = rg.read_raster(self.file.path)
        raster[np.isnan(raster)] = 0
        raster = raster.astype(float)
        raster[grid.mask] = np.nan
        raster.mask = grid.mask.copy()
        write_to_file_field(self.file, raster.write_raster, 'tiff')
        
    class Meta:
        ordering = ['coded_label__group']


class CaseStudyInput(FileBase):
    "Model for input description and storage"
    casestudy = models.ForeignKey(CaseStudy, on_delete=models.CASCADE,
                                  related_name="inputs")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    vizmode = models.IntegerField(choices=VIZMODE_CHOICES, default=0)
    class Meta:
        ordering = ['coded_label__sort_order']
        

# class CodedLabelManager(MP_NodeManager):
class CodedLabelManager(models.Manager):
    def get_dict(self):
        values = self.all().values('code', 'group', 'label')
        return {v['code']: v for v in values}

    def get_by_natural_key(self, code):
        return self.get(code=code)


# class CodedLabel(MP_Node):
class CodedLabel(models.Model):
    group = models.CharField(max_length=10, choices=CODEDLABEL_GROUP_CHOICES)
    code = models.SlugField(max_length=20, unique=True)
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    fa_class = models.CharField(max_length=64, default='fa-circle')
    sort_order = models.IntegerField(null=True, blank=True)
        
    old_label = models.CharField(max_length=100, blank=True, null=True)

    objects = CodedLabelManager()

    def __str__(self):
        return "{} | {}".format(self.group, self.label)

    def natural_key(self):
        return (self.code,)

    @property
    def filename_prefix(self):
        return "{}-{}".format(self.group, self.code)

    def get_msfd(self):
        if self.group == 'env':
            return self.env.msfd
        elif self.group == 'use':
            return self.use.msfd
        elif self.group == 'pre':
            return self.pressure.msfd
    
    class Meta:
      ordering = ['group', 'label']


class MsfdPres(models.Model):
    theme = models.CharField(max_length=100,
                             blank=True,
                             null=True)
    msfd_pressure = models.CharField(max_length=200,
                                     blank=True,
                                     null=True
                                     )

    def __str__(self):
        return "{} -> {}".format(self.theme, self.msfd_pressure)

    class Meta:
        verbose_name = "MSFD pressure"
        ordering = ['theme', 'msfd_pressure']


class Pressure(CodedLabel, MP_Node):
    node_order_by = ["code"]
    msfd = models.ForeignKey(MsfdPres,
                             on_delete=models.CASCADE)

    def __init__(self, *args, **kwargs):
        super(Pressure, self).__init__(*args, **kwargs)
        self.group = 'pre'

    def __str__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['path']


class MsfdUse(models.Model):
    theme = models.CharField(max_length=100,
                             blank=True,
                             null=True
                             )
    activity = models.CharField(max_length=200,
                                blank=True,
                                null=True
                                )

    def __str__(self):
        return "{} -> {}".format(self.theme, self.activity)

    class Meta:
        verbose_name = "MSFD Activity"
        verbose_name_plural = "MSFD Activities"
        ordering = ['theme', 'activity']


class Use(CodedLabel, MP_Node):
    node_order_by = ["code"]
    msfd = models.ForeignKey(MsfdUse,
                             on_delete=models.CASCADE)

    def __init__(self, *args, **kwargs):
        super(Use, self).__init__(*args, **kwargs)
        self.group = 'use'

    def __str__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['path']


class MsfdEnv(models.Model):
    theme = models.CharField(max_length=100,
                             blank=True,
                             null=True
                             )
    ecosystem_component = models.CharField(max_length=200,
                                         blank=True,
                                         null=True
                                         )
    feature = models.CharField(max_length=200,
                                         blank=True,
                                         null=True
                                         )
    element = models.CharField(max_length=200,
                                         blank=True,
                                         null=True
                                         )
    broad_group = models.CharField(max_length=200,
                                   blank=True,
                                   null=True
                                   )
    def __str__(self):
        return "{}{}{}{}".format(self.theme if self.theme else '-',
                                             " -> {}".format(self.ecosystem_component) if self.ecosystem_component else '',
                                             " -> {}".format(self.feature) if self.feature else '',
                                             " -> {}".format(self.element) if self.element else '',
        )

    class Meta:
        verbose_name = "MSFD environmental receptor"
        ordering = ['theme', 'ecosystem_component', 'broad_group']


class Env(CodedLabel, MP_Node):
    node_order_by = ["code"]
    msfd = models.ForeignKey(MsfdEnv,
                             on_delete=models.CASCADE)

    def __init__(self, *args, **kwargs):
        super(Env, self).__init__(*args, **kwargs)
        self.group = 'env'

    def __str__(self):
        return "%s" % self.label

    class Meta:
        verbose_name = "Environmental receptor"
        ordering = ['path']


class WeightManager(models.Manager):
    def get_matrix(self, context_label):
        qs = self.filter(context__label=context_label)
        return list(qs.values('weight',
                              'distance',
                              'confidence',
                              use_code=F('use__code'),
                              pressure_code=F('pres__code'),
                              ))

    def clone_weights(self,
                      old_context_label, new_context_label,
                      old_use_code=None, new_use_code=None,
                      old_pres_code=None, new_pres_code=None,
                      overwrite=False):
        list_created = []
        # get original sensitivities
        qs =  Weight.objects.filter(context__label=old_context_label)
        if old_use_code is not None:
            qs = qs.filter(use__code=old_use_code)
        if old_pres_code is not None:
            qs = qs.filter(pres__code=old_pres_code)

        new_context, created = Context.objects.get_or_create(label=new_context_label)

        for w in qs:
            if new_use_code is not None:
                new_use, created_use = Use.objects.get_or_create(code=new_use_code)
            else:
                new_use = w.use
            if new_pres_code is not None:
                new_pres, created_pres = Pressure.objects.get_or_create(code=new_pres_code)
            else:
                new_pres = w.pres

            try:
                existing_w = Weight.objects.get(context=new_context, use=new_use, pres=new_pres)
                if overwrite:
                    existing_w.delete()
                    existing_w = None
            except Weight.DoesNotExist:
                existing_w = False

            if not existing_w:
                w.pk = None
                w.context = new_context
                w.use = new_use
                w.pres = new_pres
                w.save()
                list_created.append([w, True])
            else:
                list_created.append([w, False])
        return list_created


class Weight(models.Model):
    """Model for storing use-specific relative pressure weights.
    """
    use = models.ForeignKey(Use, on_delete=models.CASCADE)
    pres = models.ForeignKey(Pressure, on_delete=models.CASCADE)
    weight = models.FloatField()
    distance = models.FloatField(default=0)
    context = models.ForeignKey(Context, on_delete=models.CASCADE)
    #
    confidence = models.FloatField(null=True, blank=True)
    #
    references = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    # custom manager
    objects = WeightManager()

    def __str__(self):
        return "{}: {} - {}".format(self.context, self.use,
                                     self.pres)
    class Meta:
        verbose_name = "Pressure weight"


class SensitivityManager(models.Manager):
    def get_matrix(self, context_label):
        qs = self.filter(context__label=context_label)
        return list(qs.values('sensitivity',
                              'impact_level',
                              'confidence',
                              pressure_code=F('pres__code'),
                              env_code=F('env__code'),
                              recovery_time=F('recovery'),
                              ))

    def clone_sensitivities(self,
                            old_context_label, new_context_label,
                            old_pres_code=None, new_pres_code=None,
                            old_env_code=None, new_env_code=None,
                            overwrite=False):
        list_created = []
        # get original sensitivities
        qs =  Sensitivity.objects.filter(context__label=old_context_label)
        if old_pres_code is not None:
            qs = qs.filter(pres__code=old_pres_code)
        if old_env_code is not None:
            qs = qs.filter(env__code=old_env_code)

        new_context, created = Context.objects.get_or_create(label=new_context_label)

        for s in qs:
            if new_pres_code is not None:
                new_pres, created_pres = Pressure.objects.get_or_create(code=new_pres_code)
            else:
                new_pres = s.pres
            if new_env_code is not None:
                new_env, created_env = Env.objects.get_or_create(code=new_env_code)
            else:
                new_env = s.env

            try:
                existing_s = Sensitivity.objects.get(context=new_context, env=new_env, pres=new_pres)
                if overwrite:
                    existing_s.delete()
                    existing_s = None
            except Sensitivity.DoesNotExist:
                existing_s = False

            if not existing_s:
                s.pk = None
                s.context = new_context
                s.pres = new_pres
                s.env = new_env
                s.save()
                list_created.append([s, True])
            else:
                list_created.append([s, False])
        return list_created


class Sensitivity(models.Model):
    """Model for storing sensitivities of the environmental components to
    the pressures.
    """
    pres = models.ForeignKey(Pressure, on_delete=models.CASCADE)
    env = models.ForeignKey(Env, on_delete=models.CASCADE)
    impact_level = models.FloatField(null=True, blank=True)
    recovery = models.FloatField(null=True, blank=True)
    sensitivity = models.FloatField()
    context = models.ForeignKey(Context, on_delete=models.CASCADE)
    confidence = models.FloatField(null=True, blank=True)
    #
    references = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)    

    # custom manager
    objects = SensitivityManager()

    def __str__(self):
        return "{}: {} - {}".format(self.context, self.pres,
                                     self.env)

    class Meta:
        verbose_name_plural = "Sensitivities"


class MucPotentialCOnflictManager(models.Manager):
    def get_matrix(self, context_label):
        qs = self.filter(context__label=context_label)
        return list(qs.values('score',
                              u1=F('use1__code'),
                              u2=F('use2__code'),
                              ))

    def plot_matrix(self, context_label):
        m = self.get_matrix(context_label)

    def clone_muc_potential_conflicts(self,
                                      old_context_label, new_context_label,
                                      old_use_code=None, new_use_code=None,
                                      old_new_muc_conflict=0,
                                      overwrite=False):
        list_created = []

        # get original sensitivities
        qs =  MUCPotentialConflict.objects.filter(context__label=old_context_label)
        old_use = None
        new_use = None
        if old_use_code is not None:
            old_use = Use.objects.get(code=old_use_code)
            qs1 = qs.filter(use1=old_use)
            qs2 = qs.filter(use2=old_use)
            qs = list(qs1) + list(qs2)
        if new_use_code is not None:
            new_use = Use.objects.get(code=new_use_code)

        new_context, created = Context.objects.get_or_create(label=new_context_label)

        for muc in qs:
            _use1 = muc.use1
            _use2 = muc.use2
            if new_use is not None:
                if old_use == _use1:
                    _use1 = new_use
                if old_use == _use2:
                    _use2 = new_use
            if _use1 == _use2:
                continue

            try:
                existing_muc = MUCPotentialConflict.objects.get(context=new_context, use1=_use1, use2=_use2)
                if overwrite:
                    existing_muc.delete()
                    existing_muc = None
            except MUCPotentialConflict.DoesNotExist:
                existing_muc = False

            if not existing_muc:
                muc.pk = None
                muc.context = new_context
                muc.use1 = _use1
                muc.use2 = _use2
                muc.save()
                list_created.append([muc, True])
            else:
                list_created.append([muc, False])

        # add old_use, new_use record
        if new_use is not None:
            muc, created = MUCPotentialConflict.objects.get_or_create(
                context=new_context,
                use1=new_use,
                use2=old_use,
                defaults={'score': old_new_muc_conflict})
            list_created.append([muc, created])

        return list_created


class MUCPotentialConflict(models.Model):
    context = models.ForeignKey(Context, on_delete=models.CASCADE)
    use1 = models.ForeignKey(Use, on_delete=models.CASCADE, related_name="mucscore_use1")
    use2 = models.ForeignKey(Use, on_delete=models.CASCADE, related_name="mucscore_use2")
    score = models.FloatField()

    objects = MucPotentialCOnflictManager()

    def __str__(self):
        return "{}: {} - {}".format(self.context, self.use1,
                                     self.use2)
    class Meta:
        unique_together = [['context', 'use1', 'use2']]


class Dataset(models.Model):
    slug = models.SlugField(max_length=100)
    label = models.CharField(max_length=100)
    expression = models.TextField(null=True, blank=True, verbose_name="Pre-processing expression")
    dataset_type = models.CharField(max_length=10, choices=CODEDLABEL_GROUP_CHOICES)

    def __str__(self):
        return "{} - {}".format(self.pk, self.label)

    def read_resource(self, resource):
        _resource = resource.split('.')
        typename = _resource[0]
        column = None
        if len(_resource) == 2:
            column = _resource[1]
        l = Layer.objects.get(typename=typename)

        if self.grid is not None:
            # TODO: move to  parser as soon as possible
            compute_area = False
            if 'eunismedscale' in l.typename:
                compute_area = True
            return layer_to_raster(l, self.grid, column=column, compute_area=compute_area)
        if self.res is not None:
            return layer_to_raster(l, res=self.res, column=column, eea=True)

    def get_layers_qs(self):
        layers = []
        e = Expression(self.expression, None)
        _layers = e.list()
        layers = [l[0].split('.')[0] for l in _layers]
        return Layer.objects.filter(typename__in=layers)

    def get_resources_urls(self):
        urls = {}
        for l in self.get_layers_qs():
            urls[l.typename] = ((l.get_absolute_url(),
                                 l.title))
        return urls

    def parse_expression(self):
        e = Expression(self.expression, 'self.read_resource')
        return e.parse()

    def eval_expression(self, grid=None, res=None):
        self.grid = grid
        self.res = res
        # TODO: rendere meno pericoloso
        return eval(self.parse_expression())

    @mark_safe
    def urls_tag(self):
        urls = self.get_resources_urls()
        if len(urls) > 0:
            return '; '.join(['<a href="{}">{}</a>'.format(u[0], u[1].capitalize()) for k, u in urls.items()])
        return ''

    urls_tag.short_description = 'Layers'


class CaseStudyDataset(models.Model):
    # dataset = models.ForeignKey(Dataset, blank=True, null=True)
    expression = models.TextField(null=True, blank=True,
                                  verbose_name="Pre-processing expression")
    resource_file = models.CharField(max_length=500,
                                     null=True, blank=True)
    thumbnail_url = models.CharField(max_length=500,
                                     null=True, blank=True)

    expression_hash = models.CharField(max_length=32, blank=True)

    maxvalue = models.FloatField(blank=True, null=True)
    minvalue = models.FloatField(blank=True, null=True)

    class Meta:
        abstract = True

    def get_dataset(self, res=None, grid=None):
        raster = self.eval_expression(res=res, grid=grid)
        logger.debug('get_dataset dataset={} max={} min={}'.format(self.pk,
                                                                   np.nanmax(raster),
                                                                   np.nanmin(raster)))
        return raster

    def update_dataset(self, dataset_type, res=None, grid=None):
        logger.debug('update_dataset res={} grid_input={}'.format(res, grid is not None))
        cs = self.casestudy.get_CS()
        raster = self.get_dataset(res=res, grid=grid)
        cs.add_layer(raster,
                     dataset_type,
                     self.get_lid(),
                     self.name.label)
        pass

    def save_thumbnail(self, res=None, grid=None):
        cs = self.casestudy.get_CS()
        out = cs.get_outpath('{}.png'.format(self.pk))
        plt.figure()
        d = self.get_dataset(res=res, grid=grid)
        if grid is not None:
            d.mask = ~(grid > 0)
        d.plot(cmap='jet')

        plt.savefig(out)

        self.resource_file = out
        self.thumbnail_url = out.replace('/var/www/geonode', '')
        self.save()
        return out

    @mark_safe
    def thumbnail_tag(self):
        if self.thumbnail_url is not None:
            return '<img src="{}" width="210"/>'.format(self.thumbnail_url)
        else:
            return ''
    thumbnail_tag.short_description = 'Thumbnail'

    # def dataset_urls_tag(self):
    #     if self.dataset is not None:
    #         return self.dataset.urls_tag()
    #     else:
    #         return ''
    # dataset_urls_tag.short_description = 'Layers'
    # dataset_urls_tag.allow_tags = True

    @mark_safe
    def updated_tag(self):
        if not self.expression_hash or hashlib.md5("whatever your string is").hexdigest() != self.expression_hash:
            return False
        return True

    updated_tag.short_description = 'Updated'

    def get_layers_qs(self):
        layers = []
        e = Expression(self.expression)
        _layers = e.list()
        layers = [l[0].split('.')[0] for l in _layers]
        return Layer.objects.filter(typename__in=layers)

    def get_resources_urls(self):
        expression = self.expression
        if expression is not None:
            urls = {}
            for l in self.get_layers_qs():
                urls[l.typename] = ((l.get_absolute_url(),
                                     l.title))
            return urls
        return []

    def eval_expression(self, res=None, grid=None):
        expression = self.expression
        if expression is not None:
            e = Expression(self.expression)
            return e.eval(res=res, grid=grid)
        else:
            None

    @mark_safe
    def urls_tag(self):
        # return "ciccio3"
        urls = self.get_resources_urls()
        if len(urls) > 0:
            return '; '.join(['<a href="{}">{}</a>'.format(u[0], u[1].capitalize()) for k, u in urls.items()])
        return ''

    urls_tag.short_description = 'Layers'

    def __str__(self):
        return self.name


class CaseStudyGrid(CaseStudyDataset):
    name = models.CharField(max_length=100, blank=True, null=True)
    pass

    def get_lid(self):
        return "grid"

    class Meta:
        ordering = ['name']


class CaseStudyUse(CaseStudyDataset):
    casestudy = models.ForeignKey(CaseStudy, on_delete=models.CASCADE)
    name = models.ForeignKey(Use, on_delete=models.CASCADE)

    def get_lid(self):
        return "u{}".format(self.name.pk)

    class Meta:
        ordering = ['name__label']


class CaseStudyEnv(CaseStudyDataset):
    casestudy = models.ForeignKey(CaseStudy, on_delete=models.CASCADE)
    name = models.ForeignKey(Env, on_delete=models.CASCADE)

    def get_lid(self):
        return "e{}".format(self.name.pk)

    class Meta:
        ordering = ['name__label']


class CaseStudyPressure(CaseStudyDataset):
    casestudy = models.ForeignKey(CaseStudy, on_delete=models.CASCADE)
    name = models.ForeignKey(Pressure, on_delete=models.CASCADE)
    source_use = models.ForeignKey(Use, blank=True, null=True, on_delete=models.CASCADE)

    def get_lid(self):
        if self.source_use is not None:
            uid = "u{}".format(self.source_use.pk)
        else:
            uid = ""

        return "{}p{}".format(uid, self.name.pk)

    class Meta:
        ordering = ['name__label']


class CaseStudyRun(models.Model):
    casestudy = models.ForeignKey(CaseStudy, on_delete=models.CASCADE)
    label = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(max_length=800, null=True, blank=True)
    domain_area = models.MultiPolygonField(blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True,
                              related_name='owned_casestudyrun',
                              verbose_name=_("Owner"), on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # temporary storage for uses a
    configuration = JSONField(null=True, blank=True)
    visibility = models.IntegerField(default=0, choices=VISIBILITY_CHOICES)
    runstatus = models.IntegerField(default=0, choices=RUNSTATUS_CHOICES)
    runerror = models.TextField(null=True, blank=True)
    
    def set_update_outputgrid(self):
        # TODO: this is a duplicate of set_update_grid
        if self.domain_area is None:
            return None
        else:
            gdf = _domain_area_to_gdf(self.domain_area)
            l = rg.read_df_like(self.casestudy.get_grid(), gdf)
            l.mask = l==0
            code = 'OUTPUTGRID'
            cl = CodedLabel.objects.get(code=code)
            # this override previous results
            csr_ol, created = self.layers.get_or_create(coded_label=cl)
            csr_ol.file = None
            csr_ol.thumbnail = None
            csr_ol.save()
            write_to_file_field(csr_ol.file, l.write_raster, 'tiff')
            plot_map(l, csr_ol.thumbnail, ceamaxval=None, logcolor=False)


class CaseStudyRunLayer(FileBase):
    "Model for layer description and storage"
    casestudyrun = models.ForeignKey(CaseStudyRun,
                                  on_delete=models.CASCADE,
                                  related_name="layers")
    class Meta:
        ordering = ['coded_label__group']


class CaseStudyRunInput(FileBase):
    "Model for input description and storage"
    casestudyrun = models.ForeignKey(CaseStudyRun, on_delete=models.CASCADE,
                                  related_name="inputs")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class CaseStudyRunOutputLayer(LayerInfoMixin):
    casestudyrun = models.ForeignKey(CaseStudyRun,
                                     on_delete=models.CASCADE,
                                     related_name="outputlayers"
                                     )

    class Meta:
        ordering = ['coded_label__group']

    @property
    def sld(self):
        if bool(self.file):
            r = rg.read_raster(self.file.path)
            name = f"layer_{self.pk}"
            sld = get_sld(r, name)
            return sld
        return None


class CaseStudyRunOutput(FileBase):
    casestudyrun = models.ForeignKey(CaseStudyRun,
                                     on_delete=models.CASCADE,
                                     related_name="outputs"
                                     )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['coded_label']


# @receiver(models.signals.post_delete, sender=CaseStudyLayer)
# @receiver(models.signals.post_delete, sender=CaseStudyInput)
# @receiver(models.signals.post_delete, sender=CaseStudyRunLayer)
# @receiver(models.signals.post_delete, sender=CaseStudyRunInput)
# @receiver(models.signals.post_delete, sender=CaseStudyRunOutputLayer)
# @receiver(models.signals.post_delete, sender=CaseStudyRunOutput)
# def auto_delete_file_on_delete(sender, instance, **kwargs):
#     """
#     Deletes file from filesystem
#     when corresponding `MediaFile` object is deleted.
#     """
#     if instance.file:
#         if os.path.isfile(instance.file.path):
#             os.remove(instance.file.path)
#     if instance.thumbnail:
#         if os.path.isfile(instance.thumbnail.path):
#             os.remove(instance.thumbnail.path)



class ESCapacity(models.Model):
    env = models.ForeignKey(Env, on_delete=models.CASCADE)
    # MESProv
    food_provisioning = models.FloatField(blank=True, null=True)
    raw_material = models.FloatField(blank=True, null=True)
    # MESReg
    air_quality = models.FloatField(blank=True, null=True)
    disturbance_protection = models.FloatField(blank=True, null=True)
    water_quality = models.FloatField(blank=True, null=True)
    biological_control = models.FloatField(blank=True, null=True)
    cycling_of_nutrients = models.FloatField(blank=True, null=True)
    # MESCult
    cognitive_benefits = models.FloatField(blank=True, null=True)
    leisure = models.FloatField(blank=True, null=True)
    feel_good_warm_glove = models.FloatField(blank=True, null=True, verbose_name="Feel good/warm glove")
    educational_and_research = models.FloatField(blank=True, null=True)
    non_use_ethical_values_iconic_species = models.FloatField(blank=True, null=True, verbose_name='Non use/ethical values/iconic species')
    # MESSup
    photosynthesis = models.FloatField(blank=True, null=True)
    nutrient_cycling = models.FloatField(blank=True, null=True)
    nursery = models.FloatField(blank=True, null=True)
    biodiversity = models.FloatField(blank=True, null=True)

    provisioning_gr = ['food_provisioning', 'raw_material']
    regulating_gr = ['air_quality', 'disturbance_protection', 'water_quality',
                     'biological_control', 'cycling_of_nutrients']
    cultural_gr = ['cognitive_benefits', 'leisure', 'feel_good_warm_glove',
                   'educational_and_research',
                   'non_use_ethical_values_iconic_species']
    supporting_gr = ['photosynthesis', 'nutrient_cycling',
                     'nursery', 'biodiversity']

    class Meta:
        verbose_name_plural = "ES Capacities"

    def get_capacity(self, group=None):
        val = 0
        if group is None:
            fields = self._meta.get_all_field_names()
            fields.remove('id')
            fields.remove('env')
            for f in fields:
                v = getattr(self, f)
                if v is not None:
                    val += v
            return val

        # else
        fields = getattr(self, "{}_gr".format(group))
        if fields is None:
            return None

        for f in fields:
            v = getattr(self, f)
            if v is not None:
                val += v
        return val

    @property
    def es_capacity(self):
        return self.get_capacity()

    @property
    def es_regulating(self):
        return self.get_capacity('regulating')

    @property
    def es_provisioning(self):
        return self.get_capacity('provisioning')

    @property
    def es_cultural(self):
        return self.get_capacity('cultural')

    @property
    def es_supporting(self):
        return self.get_capacity('supporting')


class DomainArea(models.Model):
    geo = models.MultiPolygonField(blank=True, null=True,
                                   help_text="polygon geometry(Lat Log WGS84)")
    label = models.CharField(max_length=100)

    def __str__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['label']


class PartracScenario(models.Model):
    label = models.CharField(max_length=100)
    # label = models.CharField(max_length=100, unique=True)
    # title = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)


class PartracTime(models.Model):
    reference_time = models.DateTimeField(null=True, blank=True)


class PartracData(models.Model):
    scenario = models.ForeignKey(PartracScenario, on_delete=models.CASCADE)
    reference_time = models.ForeignKey(PartracTime, on_delete=models.CASCADE)
    # reference_time = models.IntegerField()
    particle_id = models.IntegerField(db_index=True)
    geo = models.PointField(help_text="point geometry", srid=3035)
    depth = models.FloatField()
    grid_columnx = models.IntegerField(null=True, blank=True, db_index=True)
    grid_rowy = models.IntegerField(null=True, blank=True, db_index=True)


class PartracGrid(models.Model):
    rid = models.AutoField(primary_key=True)
    # label = models.SlugField(unique=True, default=uuid.uuid4)
    rast = models.RasterField(srid=3035)
    filename = models.TextField()
    # description = models.CharField(max_length=400, null=True, blank=True)


class PartracDataGrid(models.Model):
    scenario = models.ForeignKey(PartracScenario, on_delete=models.CASCADE)
    grid = models.ForeignKey(PartracGrid, on_delete=models.CASCADE)
    grid_columnx = models.IntegerField(null=True, blank=True, db_index=True)
    grid_rowy = models.IntegerField(null=True, blank=True, db_index=True)
    

# class CaseStudyRunLayers(models.Model):
#     lid = models.CharField(max_length=5)
#     label = models.CharField(max_length=5)
#     ltype = models.CharField(max_length=5, choices=LAYER_TYPE_CHOICES)
    
