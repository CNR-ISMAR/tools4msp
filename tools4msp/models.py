

import logging
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from django.contrib.gis.db import models
from geonode.layers.models import Layer
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from .processing import Expression
from .utils import layer_to_raster, get_sensitivities_by_rule, get_conflict_by_uses
from .casestudy import CaseStudy3 as CS
import itertools
import datetime
import hashlib

logger = logging.getLogger('tools4msp.models')

DATASET_TYPE_CHOICES = (
    ('grid', 'Grid'),
    ('use', 'Activity & Uses'),
    ('env', 'Environmental Component'),
    ('pre', 'Pressure'),
)

TOOLS4MSP_BASEDIR = '/var/www/geonode/static/cumulative_impact'


class Context(models.Model):
    """Model for storing information on data context."""
    label = models.CharField(max_length=100)
    description = models.CharField(max_length=200, null=True, blank=True)
    reference_date = models.DateField(default=datetime.date.today)

    def __unicode__(self):
        return self.label


class CaseStudy(models.Model):
    label = models.CharField(max_length=100)
    description = models.CharField(max_length=200, null=True, blank=True)
    grid_resolution = models.FloatField(default=1000, help_text='in meters')
    area_of_interest = models.MultiPolygonField(blank=True, null=True)
    is_published = models.BooleanField(_("Is Published"), default=False,
                                       help_text=_('Should this Case Study be published?'))
    tools4msp = models.BooleanField(_("Tools4MSP Case Study"), default=False,
                                    help_text=_('Is this a Tools4MSP Case Study?'))
    grid = models.ForeignKey("CaseStudyGrid", blank=True, null=True,
                             verbose_name="Area of analysis")

    # grid_dataset = models.ForeignKey("Dataset", blank=True, null=True,
    #                                  verbose_name="Area of analysis")

    # grid_output = models.ForeignKey("Dataset", blank=True, null=True,
    #                                 related_name="casestudy_output",
    #                                 verbose_name="")
    tool_coexist = models.BooleanField()
    tool_ci = models.BooleanField()
    tool_mes = models.BooleanField()

    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)

    objects = models.GeoManager()

    output_layer_model_config = None
    _output_layer_model = None

    CS = None

    def __unicode__(self):
        return self.label

    class Meta:
        verbose_name_plural = "Case studies"
        permissions = (
            ('view_casestudy', 'View case study'),
            ('download_casestudy', 'Download case study'),
            ('run_casestudy', 'Run case study'),
        )

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
        # TODO: move expression
        return self.grid.get_dataset(res=self.grid_resolution)

    def get_thumbnail_url(self):
        l = self.grid.get_layers_qs()[0]
        return l.thumbnail_url

    @property
    def thumbnail_url(self):
        return self.get_thumbnail_url()

    def thumbnail_tag(self):
        if self.thumbnail_url is not None:
            return '<img src="{}" width="200"/>'.format(self.thumbnail_url)
        else:
            return ''
    thumbnail_tag.short_description = 'Thumbnail'
    thumbnail_tag.allow_tags = True


class Pressure(models.Model):
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __unicode__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['label']


class Use(models.Model):
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __unicode__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['label']


class Env(models.Model):
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __unicode__(self):
        return "%s" % self.label

    class Meta:
        ordering = ['label']


class Weight(models.Model):
    """Model for storing use-specific relative pressure weights.
    """
    use = models.ForeignKey(Use)
    pressure = models.ForeignKey(Pressure)
    weight = models.FloatField()
    distance = models.FloatField(default=0)
    context = models.ForeignKey(Context)

    def __unicode__(self):
        return "{}: {} - {}".format(self.context, self.use,
                                     self.pressure)


class Sensitivity(models.Model):
    """Model for storing sensitivities of the environmental components to
    the pressures.
    """
    pressure = models.ForeignKey(Pressure)
    env = models.ForeignKey(Env)
    sensitivity = models.FloatField()
    context = models.ForeignKey(Context)

    def __unicode__(self):
        return "{}: {} - {}".format(self.context, self.pressure,
                                     self.env)

    class Meta:
        verbose_name_plural = "Sensitivities"


class Dataset(models.Model):
    slug = models.SlugField(max_length=100)
    label = models.CharField(max_length=100)
    expression = models.TextField(null=True, blank=True, verbose_name="Pre-processing expression")
    dataset_type = models.CharField(max_length=5, choices=DATASET_TYPE_CHOICES)

    def __unicode__(self):
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

    def urls_tag(self):
        urls = self.get_resources_urls()
        if len(urls) > 0:
            return '; '.join(['<a href="{}">{}</a>'.format(u[0], u[1].capitalize()) for k, u in urls.items()])
        return ''

    urls_tag.short_description = 'Layers'
    urls_tag.allow_tags = True


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
        print(raster.gtransform)
        cs.add_layer(raster,
                     dataset_type,
                     self.get_lid(),
                     self.name.label)
        pass

    def save_thumbnail(self, res=None, grid=None):
        cs = self.casestudy.get_CS()
        out = cs.get_outpath('{}.png'.format(self.pk))
        print(out)
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

    def thumbnail_tag(self):
        if self.thumbnail_url is not None:
            return '<img src="{}" width="210"/>'.format(self.thumbnail_url)
        else:
            return ''
    thumbnail_tag.short_description = 'Thumbnail'
    thumbnail_tag.allow_tags = True

    # def dataset_urls_tag(self):
    #     if self.dataset is not None:
    #         return self.dataset.urls_tag()
    #     else:
    #         return ''
    # dataset_urls_tag.short_description = 'Layers'
    # dataset_urls_tag.allow_tags = True

    def updated_tag(self):
        if not self.expression_hash or hashlib.md5("whatever your string is").hexdigest() != self.expression_hash:
            return False
        return True

    updated_tag.short_description = 'Updated'
    updated_tag.allow_tags = True

    def get_layers_qs(self):
        layers = []
        e = Expression(self.expression)
        _layers = e.list()
        layers = [l[0].split('.')[0] for l in _layers]
        return Layer.objects.filter(typename__in=layers)

    def get_resources_urls(self):
        urls = {}
        for l in self.get_layers_qs():
            urls[l.typename] = ((l.get_absolute_url(),
                                 l.title))
        return urls

    def eval_expression(self, res=None, grid=None):
        expression = self.expression
        if expression is not None:
            e = Expression(self.expression)
            return e.eval(res=res, grid=grid)
        else:
            None

    def urls_tag(self):
        urls = self.get_resources_urls()
        if len(urls) > 0:
            return '; '.join(['<a href="{}">{}</a>'.format(u[0], u[1].capitalize()) for k, u in urls.items()])
        return ''

    urls_tag.short_description = 'Layers'
    urls_tag.allow_tags = True

    def __unicode__(self):
        return self.name


class CaseStudyGrid(CaseStudyDataset):
    name = models.CharField(max_length=100, blank=True, null=True)
    pass

    def get_lid(self):
        return "grid"

    class Meta:
        ordering = ['name']


class CaseStudyUse(CaseStudyDataset):
    casestudy = models.ForeignKey(CaseStudy)
    name = models.ForeignKey(Use)

    def get_lid(self):
        return "u{}".format(self.name.pk)

    class Meta:
        ordering = ['name__label']


class CaseStudyEnv(CaseStudyDataset):
    casestudy = models.ForeignKey(CaseStudy)
    name = models.ForeignKey(Env)

    def get_lid(self):
        return "e{}".format(self.name.pk)

    class Meta:
        ordering = ['name__label']


class CaseStudyPressure(CaseStudyDataset):
    casestudy = models.ForeignKey(CaseStudy)
    name = models.ForeignKey(Pressure)
    source_use = models.ForeignKey(Use, blank=True, null=True)

    def get_lid(self):
        if self.source_use is not None:
            uid = "u{}".format(self.source_use.pk)
        else:
            uid = ""

        return "{}p{}".format(uid, self.name.pk)

    class Meta:
        ordering = ['name__label']


class CaseStudyRun(models.Model):
    casestudy = models.ForeignKey(CaseStudy)
    name = models.CharField(max_length=100, blank=True, null=True)
    out_ci = models.ForeignKey(Layer, blank=True, null=True, related_name='casestudyrun_ci')
    out_coexist = models.ForeignKey(Layer, blank=True, null=True, related_name='casestudyrun_coexist')
    area_of_interest = models.MultiPolygonField(blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, related_name='owned_casestudyrun',
                              verbose_name=_("Owner"))
    # temporary storage for uses a
    configuration = JSONField()


class ESCapacity(models.Model):
    env = models.ForeignKey(Env)
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

# class CaseStudyRunLayers(models.Model):
#     lid = models.CharField(max_length=5)
#     label = models.CharField(max_length=5)
#     ltype = models.CharField(max_length=5, choices=LAYER_TYPE_CHOICES)
