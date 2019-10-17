# coding: utf-8



import logging
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib import colors
import tempfile
import urllib.parse
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.list import ListView
from django.views.generic.base import ContextMixin

from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.conf import settings
from django.core.exceptions import PermissionDenied

from guardian.shortcuts import get_objects_for_user

import json


from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.embed import components
from bokeh.charts import Histogram, Bar, output_file, show, BoxPlot, HeatMap
from bokeh.models import ColumnDataSource, HoverTool, LinearColorMapper


from .casestudy import CaseStudy

from rasterio.errors import RasterioIOError
from shapely import geometry
import rectifiedgrid as rg
from mpl_toolkits import basemap
import numpy as np
from numpy import linspace
from numpy import meshgrid
import math
import pandas as pd
import copy
from os import path
from os import makedirs

from msptools.cumulative_impact.models import CICaseStudy, Sensitivity, EnvironmentalComponent, Pressure

from .models import CaseStudy as CaseStudyModel

from .models import CaseStudyRun
from .utils import raster_file_upload

logger = logging.getLogger('tools4msp.view')


# import sys
# sys.path.append('/root/ciadriplan')

# # setup
# name = 15
# adriplan_casestudy_id = name
# cellsize = 1000
# #
# version = 'v1' # rer,
# rtype = 'aditaly' # runtype
# #
# ADRIPLAN = 'http://data.adriplan.eu'
# ADRIPLAN_WMS = 'http://data.adriplan.eu/geoserver/wms?'
# mspt_basedir = '/var/www/geonode/static/cumulative_impact/'
# adriplan_html_dir = path.join(mspt_basedir, str(adriplan_casestudy_id), version, rtype) + '/'
# datadir = path.join(mspt_basedir, str(adriplan_casestudy_id), version, 'datadir') + '/'
# outputfile_prefix = 'msptools-{}-{}-{}-'.format(adriplan_casestudy_id, rtype, version)
# #
# if not path.exists(adriplan_html_dir):
#     makedirs(adriplan_html_dir)
# if not path.exists(datadir):
#     makedirs(datadir)

# # casestudy = get_adriplan_cics(adriplan_casestudy_id, cellsize, datadir=datadir, cache=True)
# # _grid = casestudy.domain_area_dataset
# # territorial_sea = get_territorialsea(_grid)
# # update_sensitivities(casestudy, adriplan_casestudy_id)
# # ci, ciuses, cienvs, confidence, scores = casestudy.cumulative_impact(outputmask=_grid==0)


class CoexistInfo(TemplateView):
    template_name = "tools4msp/coexist_info.html"


class CumulativeImpactInfo(TemplateView):
    template_name = "tools4msp/cumulative_impact_info.html"


class HomeView(TemplateView):
    template_name = "tools4msp/home.html"


class ESInfo(TemplateView):
    template_name = "tools4msp/esinfo.html"


class Tools4MPSBaseView(ContextMixin):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        self.tool = kwargs.get('tool', None)
        self.id = kwargs.get('id', None)
        self.rid = kwargs.get('rid', None)

        if self.tool == 'ci':
            self.tool_label = 'Cumulative Effects Assessment'
        elif self.tool == 'coexist':
            self.tool_label = 'Maritime Use Conflict'
        elif self.tool == 'mes':
            self.tool_label = 'Marine Ecosystem Services'

        # check per-object permission (if applicable)
        if self.id is not None:
            cs = CaseStudyModel.objects.get(pk=self.id)
            if not request.user.has_perm('run_casestudy', cs) and not cs.is_published:
                raise PermissionDenied

        return super(Tools4MPSBaseView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(Tools4MPSBaseView, self).get_context_data(**kwargs)
        context['tool'] = self.tool
        context['tool_label'] = self.tool_label

        context['id'] = self.id
        context['rid'] = self.rid
        return context


class CaseStudyListView(ListView, Tools4MPSBaseView):
    # model = CICaseStudy
    model = CaseStudyModel

    # def get_context_data(self, **kwargs):
    #     context = super(CaseStudyListView, self).get_context_data(**kwargs)
    #     return context

    # def get_context_data(self, **kwargs):
    #     tool = self.kwargs['tool']
    #     context = super(CaseStudyListView, self).get_context_data(**kwargs)
    #     context['tool'] = tool
    #     return context

    def get_queryset(self):
        tool = self.tool
        qs = self.model.objects.filter(tools4msp=True)

        if tool == 'coexist':
            qs = qs.filter(tool_coexist=True)
        if tool == 'ci':
            qs = qs.filter(tool_ci=True)
        if tool == 'mes':
            qs = qs.filter(tool_mes=True)
        qs_obj_perm = get_objects_for_user(self.request.user,
                                           'run_casestudy',
                                           qs)
        qs_published = qs.filter(is_published=True)
        return qs_published | qs_obj_perm

    # @method_decorator(login_required)
    # def dispatch(self, *args, **kwargs):
    #     return super(CaseStudyListView, self).dispatch(*args, **kwargs)

# @ensure_csrf_cookie
# @login_required
# def casestudy_configuration(request, tool, id):
#     cs = CICaseStudy.objects.get(pk=id)
#     guses = cs._group_uses()
#     genvs = cs._group_envs()
#     uses = json.dumps([{'id': guse.id, 'label': guse.label, 'selected': True} for guse in guses ])
#     envs = json.dumps([{'id': genv.id, 'label': genv.label, 'selected': True} for genv in genvs ])

#     return render(request, "tools4msp/casestudy_configuration.html",
#                   {'tool': tool,
#                    'cs': cs,
#                    'uses': uses,
#                    'envs': envs})


class CaseStudyRunConfigurationView(TemplateView, Tools4MPSBaseView):
    template_name = "tools4msp/casestudy_configuration.html"

    def get_context_data(self, **kwargs):
        context = super(CaseStudyRunConfigurationView, self).get_context_data(**kwargs)
        # cs = CICaseStudy.objects.get(pk=self.id)
        cs = CaseStudyModel.objects.get(pk=self.id)
        # get domain_area_dataset. layer
        grid_layer = cs.grid.get_layers_qs()[0]
        grid_typename = grid_layer.typename
        guses = cs.casestudyuse_set.all()
        genvs = cs.casestudyenv_set.all()
        pressures_list = cs.get_pressures_list()

        uses = json.dumps([{'id': guse.name.id,
                            'label': guse.name.label,
                            'selected': True} for guse in guses ])
        envs = json.dumps([{'id': genv.name.id,
                            'label': genv.name.label,
                            'selected': True} for genv in genvs ])
        # TODO: get presseures from sensitivities and from extra pressure layers
        press = json.dumps([{'id': p.id,
                            'label': p.label,
                            'selected': True} for p in pressures_list])
        context['cs'] = cs
        context['uses'] = uses
        context['envs'] = envs
        context['press'] = press
        context['grid_typename'] = grid_typename
        return context


@login_required
def casestudy_run_save(request, tool, id):
    logger.debug("casestudy_run_save: tool: {}, id: {}".format(tool, id))

    cs = CaseStudyModel.objects.get(pk=id)
    if not request.user.has_perm('run_casestudy', cs) and not cs.is_published:
        raise PermissionDenied

    body = json.loads(request.body)
    uses = body['uses']
    envs = body['envs']
    press = body['press']
    area = body.get('area', None)
    tools = body.get('tools', [])

    logger.debug("casestudy_run_save: uses = {}".format(uses))
    logger.debug("casestudy_run_save: envs = {}".format(envs))
    logger.debug("casestudy_run_save: press = {}".format(press))
    logger.debug("casestudy_run_save: area = {}".format(area))
    logger.debug("casestudy_run_save: tools = {}".format(tools))

    csr = CaseStudyRun(casestudy=cs)
    csr.owner = request.user
    # TODO: da ripristinare
    # if area is not None:
        # csr.area_of_interest = json.loads(area)['geometry']

    # temporary configuration
    conf = {'uses': uses,
            'envs': envs,
            'press': press}
    if area is not None:
        conf['geometry'] = json.loads(area)['geometry']
    csr.configuration = conf
    csr.save()

    aoi = None
    if area is not None:
        geo = geometry.shape(json.loads(area)['geometry'])
        geo3035 = rg.transform(geo, 3857, 3035)
        # analysis area
        res = cs.grid_resolution
        aoi = rg.read_features([(geo3035, 1)], res, 3035, eea=True)

    # area_geojson =
    # a.aa
    rtype = 'r{}'.format(csr.id)
    c = CaseStudy(None, '/var/www/geonode/static/cumulative_impact', id)
    # set the run type
    c.load_grid()
    for u in uses:
        c.load_layers("u{}".format(u))
    for u in envs:
        c.load_layers("e{}".format(u))

    pressures = ["p{}".format(p) for p in press]
    c.load_inputs()

    _grid = c.grid.copy()
    if aoi is not None:
        _grid.reproject(aoi)

    logger.debug("casestudy_run_save: grid shape {}".format(_grid.shape))

    c.rtype = rtype
    c.set_dirs()

    layer = None
    if 'ci' in tools:
        c.cumulative_impact(outputmask=_grid == 0, pressures=pressures)
        _cia = c.outputs['ci']
        # _cia.unmask(0)
        # set original extension
        if area is not None:
            cia = aoi.copy()
            cia.reproject(_cia)
        else:
            cia = _cia

        if cia.sum() > 0:
            # temp dir
            _tempdir = tempfile.mkdtemp()
            filepath = _tempdir + '/' + c.get_outfile('ci.tiff')
            cia.write_raster(filepath, dtype='float32', nodata=-9999)
            layer, style = raster_file_upload(filepath, user=request.user)
            layer.is_published = True
            layer.save()
            csr.out_ci = layer
            csr.save()

    if 'coexist' in tools:
        c.run(outputmask=_grid == 0)
        _coexista = c.outputs['coexist']
        if area is not None:
            coexista = aoi.copy()
            coexista.reproject(_coexista)
        else:
            coexista = _coexista

        if coexista.sum() > 0:
            # temp dir
            _tempdir = tempfile.mkdtemp()
            filepath = _tempdir + '/' + c.get_outfile('coexist.tiff')
            coexista.write_raster(filepath, dtype='float32', nodata=-9999)
            layer, style = raster_file_upload(filepath, user=request.user)
            layer.is_published = True
            layer.save()
            csr.out_coexist = layer
            csr.save()


    # plot = figure(title="Cell's CI score ''distribution", x_axis_label='CI score', y_axis_label='Number of cells')
    # hist, edges = np.histogram(cia[cia > 0], density=True, bins=50)
    # plot.quad(top=hist, bottom=0, left=edges[:-1], right=edges[1:],
    #           fill_color="#036564", line_color="#033649")

    reverse_url = reverse('casestudy-run-view', kwargs={'tool': tool,
                                                        'id': id,
                                                        'rid': csr.id})
    # save metadata
    tool_label = None
    if tool == 'ci':
        tool_label = 'Cumulative Impact'
    elif tool == 'coexist':
        tool_label = 'COEXIST'

    absolute_reverse_url = urllib.parse.urljoin(settings.SITEURL, reverse_url)
    abstract = 'This layer was produced using the tool "{}" and configuration and statistical outputs can be accessed here: {}'.format(tool_label,
                                                                                                                                       absolute_reverse_url)
    if layer is not None:
        layer.abstract = abstract
        layer.save()

    c.dump_outputs()
    # return HttpResponseRedirect(reverse('casestudy-run-view', args=[id, csr.id]))
    data = {'redirect': reverse_url}
    return HttpResponse(json.dumps(data), content_type='application/json')


class CaseStudyRunView(TemplateView, Tools4MPSBaseView):
    template_name = "tools4msp/casestudy_output.html"

    def get_context_data(self, **kwargs):
        context = super(CaseStudyRunView, self).get_context_data(**kwargs)

        tool = self.tool
        id = self.id
        rid = self.rid

        # cs = CICaseStudy.objects.get(pk=id)
        cs = CaseStudyModel.objects.get(pk=id)
        csr = CaseStudyRun.objects.get(pk=rid)
        c = CaseStudy(None, '/var/www/geonode/static/cumulative_impact',
                      id, rtype="r{}".format(rid))

        context["tools"] = []
        plots = {}

        # load coexist outputs
        try:
            _layers = pd.DataFrame.from_csv(c.datadir + 'layersmd.csv')
            coexista = rg.read_raster(c.get_outpath('coexist.tiff'))
            coexist_scores = pd.DataFrame.from_csv(c.get_outpath('coexist_scores.csv', rtype='full'))
            coexist_couses = pd.DataFrame.from_csv(c.get_outpath('coexist_couses_df.csv'))

            plots['hist_coexist'] = Histogram(coexista[coexista > 0],
                                              xlabel="Cell's Coexist score",
                                              ylabel="Number of cells",
                                              bins=20,
                                              plot_width=330, plot_height=300)

            a = coexist_scores.unstack().reset_index()
            a.columns = ['use1', 'use2', 'score']
            uselabels = _layers[['lid', 'label']]

            _a = pd.merge(pd.merge(a, uselabels, how="inner", left_on='use1', right_on='lid'),
                          uselabels, how="inner", left_on='use2', right_on='lid')

            hover = HoverTool(
                tooltips=[
                    ("value", "@score"),
                ]
            )

            plots['heat_coexist'] = HeatMap(_a,
                                            x='label_x',
                                            y='label_y',
                                            values='score',
                                            stat=None,
                                            tools=[hover])
            if coexist_couses.shape[0] > 1:
                hover = HoverTool(
                    tooltips=[
                        ("value", "@score"),
                    ]
                )
                plots['heat_couses'] = HeatMap(coexist_couses,
                                               x='use1',
                                               y='use2',
                                               values='score',
                                               stat=None,
                                               tools=[hover])
            else:
                plots['heat_couses'] = None

            # use_score_df = ciscores.groupby('uselabel').sum()[['score']]
            # env_score_df = ciscores.groupby('envlabel').sum()[['score']]

            # plot2 = Bar(use_score_df)
            # plot3 = Bar(env_score_df, width=800)
            # plot3.xaxis.axis_label_text_font_size = "10pt"

            context["coexistscores"] = {'total': coexista.sum()}
            context["tools"].append('coexist')
        except RasterioIOError:
            pass

        # load cumulative impact outputs
        try:
            cia = rg.read_raster(c.get_outpath('ci.tiff'))
            ciscores = pd.read_csv(c.get_outpath('ciscores.csv'))
            plots['hist_ci'] = Histogram(cia[cia > 0],
                                         xlabel="Cell's CI score",
                                         ylabel="Number of cells",
                                         bins=20,
                                         plot_width=330, plot_height=300)

            use_score_df = ciscores.groupby('uselabel').sum()[['score']]
            env_score_df = ciscores.groupby('envlabel').sum()[['score']]

            plots['bar_ci_uses'] = Bar(use_score_df, legend=False)
            plots['bar_ci_envs'] = Bar(env_score_df, width=800, legend=False)
            # plot3.xaxis.axis_label_text_font_size = "10pt"

            # sensitivities matrix
            if self.request.user.is_superuser:
                _s = pd.DataFrame.from_csv(c.get_outpath('cisensitivities.csv', rtype='full'))
                sp = _s.groupby(['uselabel', 'envlabel'])
                s = sp.agg({'score': 'sum', 'confidence': 'mean'}).reset_index()
                s['scoreround'] = s.score.round(2)

                source = ColumnDataSource(
                    data = s
                )
                colors = ["#75968f", "#a5bab7", "#c9d9d3", "#e2e2e2", "#dfccce", "#ddb7b1", "#cc7878", "#933b41", "#550b1d"]
                mapper = LinearColorMapper(palette=colors)

                opts = dict(plot_width=900, plot_height=1400,min_border=0)

                use_factors = s.sort_values('uselabel').uselabel.unique()
                env_factors = s.sort_values('envlabel').envlabel.unique()
                list(use_factors)
                p = figure(tools="hover,save", # toolbar_location=None,
                           x_range=list(use_factors), y_range=list(env_factors),
                           x_axis_location="above",
                           **opts)
                p.grid.grid_line_color = None
                p.axis.axis_line_color = None
                p.axis.major_tick_line_color = None
                p.axis.major_label_text_font_size = "7pt"
                p.axis.major_label_standoff = 0

                p.rect(x="uselabel", y="envlabel", width=1, height=1,
                       source=source,
                       fill_color={'field': 'score', 'transform': mapper},
                       # line_color=None
                   )

                p.select_one(HoverTool).tooltips = [
                    ('Use', '@uselabel'),
                    ('Env', '@envlabel'),
                    ('Score', '@score'),
                    ('Confidence', '@confidence'),
                ]

                p.text(x="uselabel", y="envlabel", source=source, text="scoreround",text_font_size="8pt", text_align="center", text_baseline="middle")
                p.xaxis.major_label_orientation = 1.
                # t = show(p, notebook_handle=True)

                plots['sensitivities'] = p

            context["ciscores"] = {'total': cia.sum()}
            context["tools"].append('ci')
        except RasterioIOError:
            pass

        script, div = components(plots, CDN)

        context["the_script"] = script
        context["the_div"] = div
        context["cs"] = cs
        context["csr"] = csr

        return context
