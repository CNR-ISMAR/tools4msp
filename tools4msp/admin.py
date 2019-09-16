from django.contrib.gis import admin
from django.utils.safestring import mark_safe
try:
    from guardian.admin import GuardedModelAdmin
except ImportError:
    GuardedModelAdmin = admin.ModelAdmin

from .models import Env, Use, Pressure, CaseStudy, \
    CaseStudyUse, CaseStudyEnv, CaseStudyPressure, \
    Dataset, ESCapacity, CaseStudyRun, Weight, Sensitivity, \
    Context, CaseStudyGrid, CaseStudyLayer, CaseStudyInput, \
    MsfdUse, MsfdPres, MsfdEnv, DomainArea, CodedLabel, \
    CaseStudyRunOutputLayer, CaseStudyRunOutput, \
    CaseStudyRunInput, CaseStudyRunLayer, \
    CaseStudyGraphic, CaseStudyRunGraphic


#############
## CaseStudy drive approach
class ContextAdmin(admin.ModelAdmin):
    model = Context

admin.site.register(Context, ContextAdmin)


class DomainAreaAdmin(admin.ModelAdmin):
    model = DomainArea

admin.site.register(DomainArea, DomainAreaAdmin)


class WeightAdmin(admin.ModelAdmin):
    model = Weight
    list_display = ['context', 'use', 'pres',
                    'weight', 'distance']
    list_filter = ['context', 'use', 'pres']

admin.site.register(Weight, WeightAdmin)


class SensitivityAdmin(admin.ModelAdmin):
    model = Sensitivity
    list_display = ['context', 'pres',
                    'env', 'sensitivity']
    list_filter = ['context', 'pres', 'env']

admin.site.register(Sensitivity, SensitivityAdmin)


class CodedLabelAdmin(admin.ModelAdmin):
    model = CodedLabel
    list_display = ['group',
                    'code',
                    'label']

admin.site.register(CodedLabel, CodedLabelAdmin)


class PresAdmin(admin.ModelAdmin):
    model = Pressure
    list_display = ['code',
                   'label',
                   'msfd']

admin.site.register(Pressure, PresAdmin)


class UseAdmin(admin.ModelAdmin):
    model = Use
    list_display = ['code',
                    'label',
                    'msfd',]

admin.site.register(Use, UseAdmin)


class EnvAdmin(admin.ModelAdmin):
    model = Env
    list_display = ['code',
                    'label',
                    'msfd',]

admin.site.register(Env, EnvAdmin)

# class CaseStudyDatasetInline(admin.TabularInline):
# fields = ('name', 'dataset', 'thumbnail_tag', 'expression_tag', 'dataset_urls_tag')
class CaseStudyDatasetInline(admin.StackedInline):
    fields = ('name',
              # 'dataset',
              'expression',
              'urls_tag',
              'thumbnail_tag',
              ('updated_tag', 'button'))
    readonly_fields = ('thumbnail_tag', 'urls_tag', 'button', 'updated_tag')
    # exclude = ('description',)
    # ordering = ('name__label',)
    classes = ('grp-open',)
    inline_classes = ('grp-collapse grp-open',)

    @mark_safe
    def button(self, obj):
        return """<button class="grp-button" type='button' onclick='tools4msp.chackValidate({});'>Update dataset</button>""".format(obj.pk)

    button.short_description = ''
    button.allow_tags = True


class CaseStudyUseInline(CaseStudyDatasetInline):
    model = CaseStudyUse


class CaseStudyEnvInline(CaseStudyDatasetInline):
    model = CaseStudyEnv


class CaseStudyPressureInline(CaseStudyDatasetInline):
    model = CaseStudyPressure
    fields = ('name',
              'source_use',
              # 'dataset',
              'expression',
              'urls_tag',
              'thumbnail_tag')


class CaseStudyLayerInline(admin.TabularInline):
    model = CaseStudyLayer

    show_change_link = True


class CaseStudyInputInline(admin.TabularInline):
    model = CaseStudyInput

    show_change_link = True


class CaseStudyGraphicInline(admin.TabularInline):
    model = CaseStudyGraphic

    show_change_link = True


class CaseStudyRunInline(admin.TabularInline):
    model = CaseStudyRun
    fields = ('label', 'owner')
    show_change_link = True


class CaseStudyAdmin(#admin.OSMGeoAdmin, # django 2.2 already provide a map widget
                     GuardedModelAdmin):
    list_display = ['label', 'is_published', 'module', 'owner']
    readonly_fields = ['thumbnail_tag']
    fields = ('label', 'description',
              'resolution',
              'domain_area',
              'domain_area_terms',
              ('domain_area_dataset', 'thumbnail_tag'),
              # 'grid_output',
              'is_published', 'module', 'cstype', 'owner')
    inlines = [
        CaseStudyLayerInline,
        CaseStudyInputInline,
        CaseStudyGraphicInline,
        CaseStudyRunInline,
        # CaseStudyUseInline,
        # CaseStudyEnvInline,
        # CaseStudyPressureInline,
        ]
    save_as = True

    filter_horizontal = ('domain_area_terms',)

    class Media:
        css = {
            "all": ("tools4msp/css/admin.css",)
        }
        js = ("tools4msp/js/admin.js",)

    def save_related(self, request, form, formsets, change):
        super(CaseStudyAdmin, self).save_related(request, form, formsets, change)
        form.instance.set_domain_area()
        form.instance.save()
        form.instance.domain_area_terms.clear()


class DatasetAdmin(admin.ModelAdmin):
    model = Dataset
    list_display = ['label', 'expression']
    # list_filter = ['dataset_type',]
    readonly_fields = ('urls_tag',)
    search_fields = ['label', 'expression']
    save_as = True


admin.site.register(CaseStudy, CaseStudyAdmin)
admin.site.register(Dataset, DatasetAdmin)


class CaseStudyGridAdmin(admin.ModelAdmin):
    model = CaseStudyGrid
    # list_display = ['id', 'name', 'expression']
    # list_filter = ['dataset_type',]
    # readonly_fields = ('thumbnail_tag', 'urls_tag', 'updated_tag')
    # search_fields = ['name', 'expression']
    # save_as = True

admin.site.register(CaseStudyGrid, CaseStudyGridAdmin)


class ESCapacityAdmin(admin.ModelAdmin):
    model = ESCapacity
    list_display = ['env', 'es_capacity', 'es_provisioning', 'es_regulating',
                    'es_cultural', 'es_supporting']
    # list_filter = ['dataset_type',]
    # readonly_fields = ('urls_tag',)
    #save_as = True
    ordering = ('env__label',)
    fieldsets = (
        (None, {
            'fields': ('env',)
        }),
        ('MES Provisioning', {
            'fields': (('food_provisioning', 'raw_material'),),
        }),
        ('MES Regulating', {
            'fields': (('air_quality', 'disturbance_protection', 'water_quality'), ('biological_control', 'cycling_of_nutrients'),
                   ),
        }),
        ('MES Cultural', {
            'fields': (('cognitive_benefits', 'leisure', 'feel_good_warm_glove'), ('educational_and_research', 'non_use_ethical_values_iconic_species'),
                   ),
        }),
        ('MES Supporting', {
            'fields': (('photosynthesis', 'nutrient_cycling'), ('nursery', 'biodiversity'),),
        })
    )
    save_as = True


#
# admin.site.register(ESCapacity, ESCapacityAdmin)
class CaseStudyRunOutputLayerAdmin(admin.ModelAdmin):
    model = CaseStudyRunOutputLayer


admin.site.register(CaseStudyRunOutputLayer, CaseStudyRunOutputLayerAdmin)


class CaseStudyRunLayerInline(admin.TabularInline):
    model = CaseStudyRunLayer


class CaseStudyRunInputInline(admin.TabularInline):
    model = CaseStudyRunInput


class CaseStudyRunGraphicInline(admin.TabularInline):
    model = CaseStudyRunGraphic


class CaseStudyRunOutputLayerInline(admin.TabularInline):
    model = CaseStudyRunOutputLayer


class CaseStudyRunOutputInline(admin.TabularInline):
    model = CaseStudyRunOutput


class CaseStudyRunAdmin(admin.ModelAdmin):
    model = CaseStudyRun
    list_display = ['id',
                    'casestudy',
                    'label']
    inlines = [
        CaseStudyRunLayerInline,
        CaseStudyRunInputInline,
        CaseStudyRunOutputLayerInline,
        CaseStudyRunOutputInline,
        CaseStudyRunGraphicInline,
    ]


admin.site.register(CaseStudyRun, CaseStudyRunAdmin)

#################
## MSFD alignment
class MsfdUseAdmin(admin.ModelAdmin):
    model = MsfdUse
    list_display = ['theme', 'activity']

admin.site.register(MsfdUse, MsfdUseAdmin)


class MsfdPresAdmin(admin.ModelAdmin):
    model = MsfdPres
    list_display = ['theme', 'msfd_pressure']

admin.site.register(MsfdPres, MsfdPresAdmin)


class MsfdEnvAdmin(admin.ModelAdmin):
    model = MsfdEnv
    list_display = ['theme', 'ecosystem_element', 'broad_group']

admin.site.register(MsfdEnv, MsfdEnvAdmin)
