from __future__ import absolute_import
from django.contrib.gis import admin
from guardian.admin import GuardedModelAdmin
from .models import Env, Use, Pressure, CaseStudy, \
    CaseStudyUse, CaseStudyEnv, CaseStudyPressure, \
    Dataset, ESCapacity, CaseStudyRun, Weight, Sensitivity, \
    Context


class ContextAdmin(admin.ModelAdmin):
    model = Context

admin.site.register(Context, ContextAdmin)


class WeightAdmin(admin.ModelAdmin):
    model = Weight
    list_display = ['context', 'use', 'pressure',
                    'weight', 'distance']
    list_filter = ['context', 'use', 'pressure']

admin.site.register(Weight, WeightAdmin)


class SensitivityAdmin(admin.ModelAdmin):
    model = Sensitivity
    list_display = ['context', 'pressure',
                    'env', 'sensitivity']
    list_filter = ['context', 'pressure', 'env']

admin.site.register(Sensitivity, SensitivityAdmin)


class PressureAdmin(admin.ModelAdmin):
    model = Pressure

admin.site.register(Pressure, PressureAdmin)


# class CaseStudyDatasetInline(admin.TabularInline):
# fields = ('name', 'dataset', 'thumbnail_tag', 'expression_tag', 'dataset_urls_tag')
class CaseStudyDatasetInline(admin.StackedInline):
    fields = ('name',
              'dataset',
              'expression',
              'urls_tag',
              'thumbnail_tag',
              ('updated_tag', 'button'))
    readonly_fields = ('thumbnail_tag', 'urls_tag', 'button', 'updated_tag')
    # exclude = ('description',)
    # ordering = ('name__label',)
    classes = ('grp-open',)
    inline_classes = ('grp-collapse grp-open',)

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
              'dataset',
              'expression',
              'urls_tag',
              'thumbnail_tag')


class CaseStudyAdmin(GuardedModelAdmin):
    list_display = ['label', 'tools4msp', 'is_published',
                    'tool_coexist', 'tool_ci', 'tool_mes']
    readonly_fields = ['thumbnail_tag']
    fields = ('label', 'description',
              'grid_resolution',
              ('grid_dataset', 'thumbnail_tag'),
              # 'grid_output',
              'tools4msp', 'is_published',
              ('tool_coexist', 'tool_ci', 'tool_mes')) #, 'area_of_interest']
    inlines = [
        CaseStudyUseInline,
        CaseStudyEnvInline,
        CaseStudyPressureInline,
        ]
    save_as = True

    class Media:
        css = {
            "all": ("tools4msp/css/admin.css",)
        }
        js = ("tools4msp/js/admin.js",)


class DatasetAdmin(admin.ModelAdmin):
    model = Dataset
    list_display = ['label', 'expression', 'dataset_type']
    list_filter = ['dataset_type',]
    readonly_fields = ('urls_tag',)
    search_fields = ['label', 'expression']
    save_as = True

admin.site.register(CaseStudy, CaseStudyAdmin)
admin.site.register(Dataset, DatasetAdmin)


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


admin.site.register(ESCapacity, ESCapacityAdmin)


class CaseStudyRunAdmin(admin.ModelAdmin):
    model = CaseStudyRun
    list_display = ['id', 'casestudy', 'name', 'out_ci']


admin.site.register(CaseStudyRun, CaseStudyRunAdmin)
