from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


# Use customized NestedViewSetMixin (see issue https://github.com/chibisov/drf-extensions/issues/142)
# from rest_framework_extensions.mixins import NestedViewSetMixin
from .drf_extensions_patch import NestedViewSetMixin

from .serializers import CaseStudySerializer, CaseStudyLayerSerializer, CaseStudyInputSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput

class CaseStudyViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudies to be viewed or edited.
    """
    queryset = CaseStudy.objects.all()
    serializer_class = CaseStudySerializer

    @action(detail=True)
    def run(self, request, *args, **kwargs):
        """
        Run the module
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        cs = self.get_object()
        return Response(cs.run())

class CaseStudyLayerViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudies to be viewed or edited.
    """
    # def get_queryset(self):
    #    return CaseStudyLayer.objects.filter(casestudy=self.kwargs['casestudy_pk'])
    queryset = CaseStudyLayer.objects.all()
    serializer_class = CaseStudyLayerSerializer


class CaseStudyInputViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudies to be viewed or edited.
    """
    queryset = CaseStudyInput.objects.all()
    serializer_class = CaseStudyInputSerializer