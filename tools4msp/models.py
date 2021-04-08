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

from jsonfield import JSONField
from .processing import Expression
from .utils import layer_to_raster, get_sensitivities_by_rule, get_conflict_by_uses, get_layerinfo
from .modules.casestudy import CaseStudyBase as CS
import itertools
import datetime
import hashlib
from django.contrib.gis.geos import MultiPolygon
from django.db.models import F
from django.core.files import File
from io import StringIO
import json
from django.dispatch import receiver
import os
from .utils import write_to_file_field, plot_heatmap
from .plotutils import plot_map, get_map_figure_size, get_zoomlevel
from django.conf import settings
from .modules.cea import CEACaseStudy
from .modules.muc import MUCCaseStudy
from .modules.partrac import ParTracCaseStudy
from os import path
import pandas as pd
import cartopy
import cartopy.io.img_tiles as cimgt
import matplotlib.animation as animation
import numpy as np
import rectifiedgrid as rg
from django.core.exceptions import ObjectDoesNotExist
import math
from .modules.sua import run_sua
import uuid

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
)

MODULE_TYPE_CHOICES = (
    ('cea', 'CEA'),
    ('muc', 'MUC'),
    ('partrac', 'Particle tracking'),
)

CASESTUDY_TYPE_CHOICES = (
    ('default', 'Default run'),
    ('customized', 'Customized run'),
)


TOOLS4MSP_BASEDIR = '/var/www/geonode/static/cumulative_impact'

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

class Context(models.Model):
    """Model for storing information on data context."""
    label = models.CharField(max_length=100)
    description = models.CharField(max_length=400, null=True, blank=True)
    reference_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return self.label


def _run_sua(csr, nparams=20, nruns=100, bygroup=True, njobs=1):
    if isinstance(csr, int):
        csr = CaseStudyRun.objects.get(pk=csr)
    selected_layers = csr.configuration['selected_layers']
    uses, pres, envs = check_coded_labels(selected_layers)
    kwargs_run = {'uses': uses, 'pressures': pres, 'envs': envs}
    module_cs = csr.casestudy.module_cs
    module_cs_sua = run_sua(module_cs, nparams=nparams,
                            nruns=nruns, bygroup=bygroup, njobs=njobs,
                            kwargs_run=kwargs_run)

    layers = {'MAPCEA-SUA-MEAN': module_cs_sua.mean,
              'MAPCEA-SUA-CV': module_cs_sua.cv,}
    for code, l in layers.items():
        cl = CodedLabel.objects.get(code=code)
        csr_ol = csr.outputlayers.create(coded_label=cl)
        write_to_file_field(csr_ol.file, l.write_raster, 'geotiff')
        plot_map(l, csr_ol.thumbnail, ceamaxval=None, logcolor=False)

    return module_cs


def _run(csr, runtypelevel=3):
    selected_layers = csr.configuration['selected_layers']
    module_cs = csr.casestudy.module_cs
    uses, pres, envs = check_coded_labels(selected_layers)

    if csr.casestudy.module == 'cea':
        module_cs.load_layers()
        module_cs.load_grid()
        module_cs.load_inputs()
        module_cs.run(uses=uses, envs=envs, pressures=pres, runtypelevel=runtypelevel)
        # Collect and save outputs

        # CEASCORE map
        ci = module_cs.outputs['ci']
        cl = CodedLabel.objects.get(code='CEASCORE')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        csr_o = csr.outputs.create(coded_label=cl)
        write_to_file_field(csr_ol.file, ci.write_raster, 'geotiff')
        plt.figure(figsize=get_map_figure_size(ci.bounds))
        ax, mapimg = ci.plotmap(#ax=ax,
                   cmap='jet',
                   logcolor=True,
                   legend=True,
                   # maptype='minimal',
                   grid=True,
                   gridrange=1)
        ax.add_image(cimgt.Stamen('toner-lite'), get_zoomlevel(ci.geobounds))

        if runtypelevel >= 3:
            # CEASCORE map as png for
            write_to_file_field(csr_ol.thumbnail, plt.savefig, 'png', dpi=300)
            plt.clf()
            plt.close()

        #PRESENVSCEA heatmap
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
                'pescore': float(l.sum())
            })
            totscore += l.sum()
        write_to_file_field(csr_o.file, lambda buf: json.dump(pescore, buf), 'json', is_text_file=True)

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
            return module_cs

        # WEIGHTS
        cl = CodedLabel.objects.get(code='WEIGHTS')
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

        # PRESCORE barplot
        cl = CodedLabel.objects.get(code='BARPRESCORE')
        csr_o = csr.outputs.create(coded_label=cl)
        out_pressures = module_cs.outputs['pressures']
        _pscores = [{'p': k, 'pscore': float(l.sum())} for (k, l) in out_pressures.items() if l.sum()>0]
        write_to_file_field(csr_o.file, lambda buf: json.dump(_pscores, buf), 'json', is_text_file=True)
        pscores = pd.DataFrame(_pscores)
        
        pscores.set_index('p', inplace=True)
        ax = pscores.plot.bar(legend=False)
        ax.set_xlabel('Pressures')
        ax.set_ylabel('pressure score')
        totscoreperc = pscores.pscore.sum()/100
        y1, y2 = ax.get_ylim()
        x1, x2= ax.get_xlim()
        ax2 = ax.twinx()
        ax2.set_ylim(y1/totscoreperc, y2/totscoreperc)
        ax2.set_ylabel('% of the total pressure score')
            
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        #USEPRESCORE heatmap
        cl = CodedLabel.objects.get(code='HEATUSEPRESCORE')
        csr_o = csr.outputs.create(coded_label=cl)
        out_usepressures = module_cs.outputs['usepressures']
        _upscores = []
        totscore = 0
        for (k, l) in out_usepressures.items():
            (u, p) = k.split('--')
            if l.sum() == 0:
                continue
            _upscores.append({
                'u': u,
                'p': p,
                'upscore': float(l.sum())
            })
            totscore += l.sum()
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
                'uescore': float(l.sum())
            })
            totscore += l.sum()
        write_to_file_field(csr_o.file, lambda buf: json.dump(uescore, buf), 'json', is_text_file=True)
        ax = plot_heatmap(uescore, 'u', 'e', 'uescore', scale_measure=totscore / 100, fmt='.1f', fillval=0, cbar=False, figsize=[8, 10])
        ax.set_title('CEA score (%)')
        ax.set_xlabel('Human uses')
        ax.set_ylabel('Environmental receptors')
        plt.tight_layout()
        write_to_file_field(csr_o.thumbnail, plt.savefig, 'png')
        plt.clf()
        plt.close()

        
        ceamaxval = ci.max()
        MSFDGROUPS = {'Biological': 'MAPCEA-MSFDBIO',
                      'Physical': 'MAPCEA-MSFDPHY',
                      'Substances, litter and energy': 'MAPCEA-MSFDSUB'}
        for ptheme, msfdcode in MSFDGROUPS.items():
            plist = list(Pressure.objects.filter(msfd__theme=ptheme).values_list('code', flat=True))
            module_cs.run(uses=uses, envs=envs, pressures=plist)
            #
            ci = module_cs.outputs['ci']
            cl = CodedLabel.objects.get(code=msfdcode)

            plist_str = ", ".join(CodedLabel.objects.filter(code__in=plist).values_list('label', flat=True))
            description = 'MSFD {} pressures: {}'.format(ptheme, plist_str)
            csr_ol = csr.outputlayers.create(coded_label=cl, description=description)
            write_to_file_field(csr_ol.file, ci.write_raster, 'geotiff')

            plot_map(ci, csr_ol.thumbnail, ceamaxval=ceamaxval)

    elif csr.casestudy.module == 'muc':
        csr.casestudy.set_or_update_context('AIR')
        module_cs.load_layers()
        module_cs.load_grid()
        module_cs.load_inputs()
        module_cs.run(uses=uses)
        totalscore = module_cs.outputs['muc_totalscore']

        # MUCSCORE map
        out = module_cs.outputs['muc']
        cl = CodedLabel.objects.get(code='MUCSCORE')
        csr_ol = csr.outputlayers.create(coded_label=cl)
        write_to_file_field(csr_ol.file, out.write_raster, 'geotiff')
        plt.figure(figsize=get_map_figure_size(out.bounds))
        ax, mapimg = out.plotmap(#ax=ax,
                   cmap='jet',
                   logcolor=True,
                   legend=True,
                   # maptype='minimal',
                   grid=True, gridrange=1)
        ax.add_image(cimgt.Stamen('toner-lite'), get_zoomlevel(out.geobounds))
        # CEASCORE map as png for
        write_to_file_field(csr_ol.thumbnail, plt.savefig, 'png')
        plt.clf()

        # PCONFLICT
        cl = CodedLabel.objects.get(code='PCONFLICT')
        csr_o = csr.outputs.create(coded_label=cl)
        pconflict = MUCPotentialConflict.objects.get_matrix('AIR')
        write_to_file_field(csr_o.file, lambda buf: json.dump(pconflict, buf), 'json', is_text_file=True)
        ax = plot_heatmap(pconflict, 'u1', 'u2', 'score',
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
        return module_cs

    elif csr.casestudy.module == 'partrac':
        # module_cs.load_layers()
        module_cs.load_grid()
        module_cs.load_inputs()
        module_cs.run(scenario=1)
        time_rasters = module_cs.outputs['time_rasters']
        # collect statistics
        vmaxcum = np.asscalar(max([r[1].max() for r in time_rasters]))
        vmax = np.asscalar(max([r[2].max() for r in time_rasters]))

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
            else:
                ax.add_image(cimgt.Stamen('toner-lite'), get_zoomlevel(raster.geobounds))
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

        write_to_file_field(csr_o.file, time_rasters[-1][1].copy().write_raster, 'geotiff')

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
        write_to_file_field(csr_o.file, time_rasters[-1][2].copy().write_raster, 'geotiff')

        return module_cs
        #
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
    return module_cs


def check_coded_labels(selected_layers):
    uses = None
    envs = None
    pres = None
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
        if len(uses) == 0:
            uses = None
        if len(envs) == 0:
            envs = None
        if len(pres) == 0:
            pres = None
    return uses, pres, envs


class CaseStudy(models.Model):
    # id = models.AutoField(primary_key=True, help_text="AAAAAAAAA") # TODO: to be removed
    label = models.CharField(max_length=100, help_text="CaseStudy title")
    description = models.CharField(max_length=400, null=True, blank=True, help_text="CaseStudy description")

    cstype = models.CharField(_('CS Type'), max_length=10, choices=CASESTUDY_TYPE_CHOICES,
                              help_text="CaseStudy type. Accepted values are: {}".format(", ".join([t[0] for t in CASESTUDY_TYPE_CHOICES])))
    module = models.CharField(_('Module type'), max_length=10, choices=MODULE_TYPE_CHOICES,
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

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    owner = models.ForeignKey('auth.User',
                              on_delete=models.CASCADE)
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
            geounion = geounion.simplify(0.01)
            if geounion.geom_type != 'MultiPolygon':
                geounion = MultiPolygon(geounion)
            self.domain_area = geounion

    def set_or_update_context(self, context_label):
        # TODO: this is a module-aware function. Move to the module library
        # set sensitivity
        cl = CodedLabel.objects.get(code='SENS')
        csi, created = self.inputs.get_or_create(coded_label=cl)
        s = Sensitivity.objects.get_matrix(context_label)
        jsonstring = json.dumps(s)
        # only the file extension matters
        csi.file.save('file.json', File(StringIO(jsonstring)))

        # weights
        cl = CodedLabel.objects.get(code='WEIGHTS')
        csi, created = self.inputs.get_or_create(coded_label=cl)
        s = Weight.objects.get_matrix(context_label)
        jsonstring = json.dumps(s)
        # only the file extension matters
        csi.file.save('file.json', File(StringIO(jsonstring)))

        # muc potential conflict matrix
        cl = CodedLabel.objects.get(code='PCONFLICT')
        csi, created = self.inputs.get_or_create(coded_label=cl)
        s = MUCPotentialConflict.objects.get_matrix(context_label)
        jsonstring = json.dumps(s)
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

    def run(self, selected_layers=None, runtypelevel=3):
        if self.module in ['cea', 'muc', 'partrac']:
            conf = {'selected_layers': selected_layers,
                    'runtypelevel': runtypelevel}
            csr = self.casestudyrun_set.create(configuration=conf)

            _run(csr, runtypelevel=runtypelevel)
            rlist = self.casestudyrun_set.filter(pk=csr.pk)
        else:
            import time
            time.sleep(5)
            rlist = self.casestudyrun_set.all()
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
    name = "{}-{}".format(self.coded_label.group,
                          self.coded_label.code)
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
                                                                                  'partrac']},
                                   on_delete=models.CASCADE)
    description = models.CharField(max_length=400, null=True, blank=True)
    file = models.FileField(blank=True,
                            null=True,
                            upload_to=generate_filename)
    thumbnail = models.ImageField(blank=True,
                            null=True,
                            upload_to=generate_filename)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


## TODO: add constrain to avoid multiple CaseStudyLayer with the same coded_label
class CaseStudyLayer(FileBase):
    "Model for layer description and storage"
    casestudy = models.ForeignKey(CaseStudy,
                                  on_delete=models.CASCADE,
                                  related_name="layers")
    layerinfo = JSONField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.coded_label is not None:
            try:
                self.layerinfo = get_layerinfo(self.file.path)
            except ValueError:
                pass
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['coded_label__group']


class CaseStudyInput(FileBase):
    "Model for input description and storage"
    casestudy = models.ForeignKey(CaseStudy, on_delete=models.CASCADE,
                                  related_name="inputs")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class CodedLabelManager(models.Manager):
    def get_dict(self):
        values = self.all().values('code', 'group', 'label')
        return {v['code']: v for v in values}

    def get_by_natural_key(self, code):
        return self.get(code=code)


class CodedLabel(models.Model):
    group = models.CharField(max_length=10, choices=CODEDLABEL_GROUP_CHOICES)
    code = models.SlugField(max_length=15, unique=True)
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    old_label = models.CharField(max_length=100, blank=True, null=True)

    objects = CodedLabelManager()

    def __str__(self):
        return "{} | {}".format(self.group, self.label)

    def natural_key(self):
        return (self.code,)

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


class Pressure(CodedLabel):
    msfd = models.ForeignKey(MsfdPres,
                             on_delete=models.CASCADE)

    def __init__(self, *args, **kwargs):
        super(Pressure, self).__init__(*args, **kwargs)
        self.group = 'pre'

    def __str__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['label']


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


class Use(CodedLabel):
    msfd = models.ForeignKey(MsfdUse,
                             on_delete=models.CASCADE)

    def __init__(self, *args, **kwargs):
        super(Use, self).__init__(*args, **kwargs)
        self.group = 'use'

    def __str__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['label']


class MsfdEnv(models.Model):
    theme = models.CharField(max_length=100,
                             blank=True,
                             null=True
                             )
    ecosystem_element = models.CharField(max_length=200,
                                         blank=True,
                                         null=True
                                         )
    broad_group = models.CharField(max_length=200,
                                   blank=True,
                                   null=True
                                   )
    def __str__(self):
        return "{} -> {} -> {}".format(self.theme,
                                 self.ecosystem_element,
                                 self.broad_group)

    class Meta:
        verbose_name = "MSFD environmental receptor"
        ordering = ['theme', 'ecosystem_element', 'broad_group']


class Env(CodedLabel):
    msfd = models.ForeignKey(MsfdEnv,
                             on_delete=models.CASCADE)

    def __init__(self, *args, **kwargs):
        super(Env, self).__init__(*args, **kwargs)
        self.group = 'env'

    def __str__(self):
        return "%s" % self.label

    class Meta:
        verbose_name = "Environmental receptor"
        ordering = ['label']


class WeightManager(models.Manager):
    def get_matrix(self, context_label):
        qs = self.filter(context__label=context_label)
        return list(qs.values(u=F('use__code'),
                              p=F('pres__code'),
                              w=F('weight'),
                              d=F('distance')))

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
                new_use = Use.objects.get_or_create(code=new_use_code)
            else:
                new_use = w.use
            if new_pres_code is not None:
                new_pres = Pressure.objects.get_or_create(code=new_pres_code)
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
        return list(qs.values(p=F('pres__code'),
                              e=F('env__code'),
                              s=F('sensitivity'),
                              c=F('confidence'),
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
                new_pres = Pressure.objects.get_or_create(code=new_pres_code)
            else:
                new_pres = s.pres
            if new_env_code is not None:
                new_env = Env.objects.get_or_create(code=new_env_code)
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
    dataset_type = models.CharField(max_length=5, choices=CODEDLABEL_GROUP_CHOICES)

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
                                                                   raster.max(),
                                                                   raster.min()))
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
    description = models.CharField(max_length=400, null=True, blank=True)
    domain_area = models.MultiPolygonField(blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True,
                              related_name='owned_casestudyrun',
                              verbose_name=_("Owner"), on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # temporary storage for uses a
    configuration = JSONField(null=True, blank=True)


class CaseStudyRunLayer(FileBase):
    "Model for layer description and storage"
    casestudy = models.ForeignKey(CaseStudyRun,
                                  on_delete=models.CASCADE)
    class Meta:
        ordering = ['coded_label__group']


class CaseStudyRunInput(FileBase):
    "Model for input description and storage"
    casestudy = models.ForeignKey(CaseStudyRun, on_delete=models.CASCADE,
                                  related_name="inputs")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class CaseStudyRunOutputLayer(FileBase):
    casestudyrun = models.ForeignKey(CaseStudyRun,
                                     on_delete=models.CASCADE,
                                     related_name="outputlayers"
                                     )
    class Meta:
        ordering = ['coded_label__group']


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
