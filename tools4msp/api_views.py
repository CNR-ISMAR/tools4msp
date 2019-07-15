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

    retrieve:
        Return a user instance.

    list:
        Return the list of available CaseStudies.

    create:
        Add a new Case Study
        Adds a new Case Study to the server. To ad additional inputs use the following methods:
        * see [/casestudies/{casestudyName}/layers](#/Layers/postCaseStudyLayers) for adding a new Layer
        * see [/casestudies/{casestudyName}/inputs](#/Layers/postCaseStudyInputs) from adding new input parameters or datasets

    delete:
        Remove an existing user.

    partial_update:
        Update one or more fields on an existing user.

    update:
        Update a user.

    parameters:
        - name: name
            type: string
            required: true
            location: form
        - name: bloodgroup
            type: string
            required: true
            location: form
        - name: birthmark
            type: string
            required: true
            location: form
    """
    queryset = CaseStudy.objects.all()
    serializer_class = CaseStudySerializer
    filterset_fields = ('cstype', 'module')

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
    API endpoint that allows CaseStudy Layers to be viewed or edited.
    """
    # def get_queryset(self):
    #    return CaseStudyLayer.objects.filter(casestudy=self.kwargs['casestudy_pk'])
    queryset = CaseStudyLayer.objects.all()
    serializer_class = CaseStudyLayerSerializer


class CaseStudyInputViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudy Input datasets to be viewed or edited.
    """
    queryset = CaseStudyInput.objects.all()
    serializer_class = CaseStudyInputSerializer