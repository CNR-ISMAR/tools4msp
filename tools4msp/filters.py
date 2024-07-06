import django_filters
from django.contrib.postgres.search import SearchVector
from django.db.models import Q
from tools4msp.models import CaseStudy, CodedLabel, Context


class CodedLabelFilter(django_filters.FilterSet):
    case_study_id = django_filters.NumberFilter(method='filter_case_study')
    search = django_filters.CharFilter(method='filter_search')

    def filter_case_study(self, queryset, name, value):        
        # TODO: solo per CEA
        cs = CaseStudy.objects.get(pk=value)
        groups = []
        if cs.module == 'cea':
            c = cs.default_context
            # get usepre
            pcvals = c.weight_set.all().distinct().values_list('pres__code', flat=True)
            regex = '^.*(--%s).*$' % '|'.join(['--'+ p for p in pcvals])
            _filter = Q(code__regex=regex)
            # get env
            _filter |= Q(env__sensitivity__context=c)
            # get use
            _filter |= Q(use__weight__context=c)
            # add additional from the context
            _filter |= Q(code__in=['OUTPUTGRID'])
            CodedLabel.objects.filter(_filter).distinct()
            ids = cs.layers.all().values_list('coded_label_id', flat=True)
            return queryset.filter(_filter).exclude(id__in=ids).distinct()

            groups = ['casestudy', 'env', 'use']
        elif cs.module == 'muc':
            groups = ['use']
        elif cs.module == 'pmar':
            groups = ['casestudy', 'use']
        elif cs.module == 'geodatamaker':
            groups = ['casestudy', 'use', 'env', 'pre', 'usepre']
        ids = cs.layers.all().values_list('coded_label_id', flat=True)
        return queryset.filter(group__in=groups).exclude(id__in=ids)

    # TODO: cambiare anche per le altre classi questo modo di fare
    # search_filter, cosi viene pubblicato nelle API
    def filter_search(self, queryset, name, value):
        return queryset.filter(
                        Q(group__icontains=value) | Q(code__icontains=value) | Q(label__icontains=value)
                    )

    class Meta:
        model = CodedLabel
        fields = ['group']


class ContextFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_search')

    def filter_search(self, queryset, name, value):
        return queryset.filter(
                        Q(label__icontains=value) | Q(description__icontains=value)
                    )
    
    class Meta:
        model = Context
        fields = ['label']
