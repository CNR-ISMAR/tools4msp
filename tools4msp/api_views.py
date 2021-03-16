# ensure matplotlib import and setup at the very beginning
import matplotlib
matplotlib.use('agg')

from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework.decorators import action, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FileUploadParser, ParseError
from rest_framework import status
import coreapi, coreschema
from rasterio.io import MemoryFile
from rasterio.errors import RasterioIOError
import json

# Use customized NestedViewSetMixin (see issue https://github.com/chibisov/drf-extensions/issues/142)
# from rest_framework_extensions.mixins import NestedViewSetMixin
from .drf_extensions_patch import NestedViewSetMixin

from .serializers import CaseStudySerializer, CaseStudyLayerSerializer, CaseStudyInputSerializer, \
    CaseStudyListSerializer, DomainAreaSerializer, DomainAreaListSerializer, CodedLabelSerializer, \
    FileUploadSerializer, CaseStudyRunSerializer, ThumbnailUploadSerializer, CaseStudyCloneSerializer, \
    ContextSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput, DomainArea, CodedLabel, \
    CaseStudyRun, Context
from rest_framework.schemas import AutoSchema



class ActionSerializerMixin(object):
    action_serializers = {}
    def get_serializer_class(self):
        if self.action in self.action_serializers:
            return self.action_serializers.get(self.action, None)
        else:
            return super().get_serializer_class()


class DomainAreaViewSet(ActionSerializerMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DomainArea.objects.all()
    serializer_class = DomainAreaSerializer
    action_serializers = {'list': DomainAreaListSerializer}
    filterset_fields = ('label',)


class CodedLabelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CodedLabel.objects.all()
    serializer_class = CodedLabelSerializer
    lookup_field = 'code'


class ContextViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Context.objects.all()
    serializer_class = ContextSerializer


class CaseStudyViewSet(NestedViewSetMixin, ActionSerializerMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudies to be viewed or edited.

    retrieve:
    Return a CaseStudy instance.

    list:
    Return the list of available CaseStudies.

    create:
    Add a new Case Study
    Adds a new Case Study to the server. To add additional inputs use the following methods:

    * see [/casestudies/{casestudyId}/layers](#api-casestudies-layers-create) for adding a new Layer
    * see [/casestudies/{casestudyId}/inputs](#api-casestudies-inputs-create) from adding new input parameters or datasets

    delete:
    Remove an existing CaseStudy.

    partial_update:
    Update one or more fields on an existing CaseStudy.

    update:
    Update a CaseStudy.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CaseStudySerializer
    filterset_fields = ('cstype', 'module', 'tag')

    # used by Mixin to implement multiple serializer
    action_serializers = {'list': CaseStudyListSerializer,
                          'cloneupdate': CaseStudyCloneSerializer}

    # def retrieve(self, request, *args, **kwargs):
    #     return super().retrieve(request, *args, **kwargs)

    # this is important to allow correct schema generation
    queryset = CaseStudy.objects.all()

    def get_queryset(self):
        """
        This view should return a list of all the CaseStudies
        for the currently authenticated user.
        """
        queryset = self.queryset #CaseStudy.objects.all()
        # this need for avoid incompatibility with schema generator of django_filter
        if self.request is None:
            return queryset.none()
        elif not self.request.user.is_superuser:
            return queryset.filter(owner=self.request.user)
        else:
            return queryset

    def perform_create(self, serializer):
        cs = serializer.save(owner=self.request.user)
        # TODO: try to avoid double save
        cs.set_domain_area()
        cs.save()

    run_schema = AutoSchema(
        manual_fields=[
            coreapi.Field(
                "selected_layers",
                schema=coreschema.String(description="Comma-separated list of layer codes"),
                required=False,
                location='query'
            ),
            coreapi.Field(
                "runtypelevel",
                schema=coreschema.String(description="Level of run type: 3 (default)"),
                required=False,
                location='query'
            ),
        ]
    )
    @action(detail=True, schema=run_schema)
    def run(self, request, *args, **kwargs):
        """
        Execute an analysis for the current CaseStudy according to the CaseStudy configuration. The reference to a new CaseStudyRun will be returned.
        """
        selected_layers = self.request.GET.get('selected_layers')
        if selected_layers is not None:
            selected_layers = selected_layers.split(',')

        runtypelevel = int(self.request.GET.get('runtypelevel', 3))
        # check for valid runtypelevels
        # raise ParseError("Invalid runtypelevel parameter")

        rjson = {'success': False}
        cs = self.get_object()
        csr = cs.run(selected_layers=selected_layers, runtypelevel=runtypelevel)
        csr.owner = request.user
        csr.save()
        if csr is not None:
            csr_serializer = CaseStudyRunSerializer(csr, context={'request': request})

            rjson['success'] = True
            rjson['run'] = csr_serializer.data['url']
            rjson['run_id'] = csr.pk
            rjson['selected_layers'] = selected_layers

        return Response(rjson)

    @action(detail=True,
            url_path='setcontext/(?P<context_label>[^/.]+)')
    def setcontext(self, request, context_label, *args, **kwargs):
        """
        Set the input parameters for the current CaseStudy according to the specified context (see. thesaurus of available Contexts).
        """
        context = Context.objects.get(label=context_label)

        cs = self.get_object()
        cs.set_or_update_context(context_label)
        rjson = {'success': True,
                 'context' : context_label}
        return Response(rjson)

    @action(detail=True, methods=['post'])
    def cloneupdate(self, request, *args, **kwargs):
        """
        Clone/duplicate the CaseStudy allowing the updating of parameters/metadata. The reference to the new CaseStudy will be returned.
        """

        cs_clone_serializer = CaseStudyCloneSerializer(data=request.data)
        if not cs_clone_serializer.is_valid():
            return Response(cs_clone_serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)


        rjson = {'success': False}
        _cs = self.get_object()

        cs = _cs.clone()

        cs.owner = request.user
        cs.cstype = 'customized'

        if cs_clone_serializer.data['label'] is not None:
            cs.label = cs_clone_serializer.data['label']
        if cs_clone_serializer.data['description'] is not None:
            cs.description = cs_clone_serializer.data['description']
        if cs_clone_serializer.data['tag'] is not None:
            cs.tag = cs_clone_serializer.data['tag']
        cs.save()

        cs_serializer = CaseStudySerializer(cs, context={'request': request})

        rjson['success'] = True
        rjson['url'] = cs_serializer.data['url']
        rjson['id'] = cs.pk

        return Response(rjson)

    @action(detail=True)
    def clone(self, request, *args, **kwargs):
        """
        [DEPRECATED: see cloneupdate] Clone/duplicate the CaseStudy. The reference to the new CaseStudy will be returned.
        """

        rjson = {'success': False}
        _cs = self.get_object()

        cs = _cs.clone()

        cs.owner = request.user
        cs.cstype = 'customized'
        cs.save()

        cs_serializer = CaseStudySerializer(cs, context={'request': request})

        rjson['success'] = True
        rjson['url'] = cs_serializer.data['url']
        rjson['id'] = cs.pk

        return Response(rjson)


class CaseStudyLayerViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudyLayers to be viewed or edited.
    """
    # def get_queryset(self):
    #    return CaseStudyLayer.objects.filter(casestudy=self.kwargs['casestudy_pk'])
    queryset = CaseStudyLayer.objects.all()
    serializer_class = CaseStudyLayerSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['put'], serializer_class=FileUploadSerializer)
    @parser_classes([FileUploadParser])
    def upload(self, request, *args, **kwargs):
        """
        Upload a geotiff file into a CaseStudyLayer object. Projection, extension and resolution should
        be the same for all layers.

        Basic usage example in python
        ```python
        import requests
        url = "https://api.tools4msp.eu/api/casestudies/{parent_lookup_casestudy__id}/layers/{id}/upload/
        input_file = "[path to the geotiff file]"

        with open(input_file, 'rb') as f:
            files = {'file': f}
            r = requests.put(url, auth=('Token', TOKEN), files=files)
        ```
        """
        if 'file' not in request.data:
            raise ParseError("Empty content")

        f = request.data['file']
        with MemoryFile(f) as memfile:
            try:
                with memfile.open() as dataset:
                    pass
            except RasterioIOError:
                raise ParseError("Unsupported raster file")

        obj = self.get_object()
        obj.file.save(f.name, f, save=True)
        return Response(status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'], serializer_class=ThumbnailUploadSerializer)
    @parser_classes([FileUploadParser])
    def tupload(self, request, *args, **kwargs):
        """
        Upload a thumbnail image (eg. png) into a CaseStudyLayer object.

        Basic usage example in python
        ```python
        import requests
        url = "https://api.tools4msp.eu/api/casestudies/{parent_lookup_casestudy__id}/layers/{id}/tupload/
        input_file = "[path to the thumbnail image]"

        with open(input_file, 'rb') as f:
            files = {'file': f}
            r = requests.put(url, auth=('Token', TOKEN), files=files)
        ```
        """
        if 'file' not in request.data:
            raise ParseError("Empty content")

        f = request.data['file']

        obj = self.get_object()
        obj.thumbnail.save(f.name, f, save=True)
        return Response(status=status.HTTP_201_CREATED)


class CaseStudyInputViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudyInput datasets to be viewed or edited.
    """
    queryset = CaseStudyInput.objects.all()
    serializer_class = CaseStudyInputSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['put'], serializer_class=FileUploadSerializer)
    @parser_classes([FileUploadParser])
    def upload(self, request, *args, **kwargs):
        """
        Upload an input parameters file (JSON) into a CaseStudyInput object.

        Basic usage example in python
        ```python
        import requests
        url = "https://api.tools4msp.eu/api/casestudies/{parent_lookup_casestudy__id}/inputs/{id}/upload/
        input_file = "[path to the JSON file]"

        with open(input_file, 'rb') as f:
            files = {'file': f}
            r = requests.put(url, auth=('Token', TOKEN), files=files)
        ```
        """
        if 'file' not in request.data:
            raise ParseError("Empty content")

        f = request.data['file']

        obj = self.get_object()
        obj.file.save(f.name, f, save=True)
        return Response(status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'], serializer_class=ThumbnailUploadSerializer)
    @parser_classes([FileUploadParser])
    def tupload(self, request, *args, **kwargs):
        """
        Upload a thumbnail image (eg. png) into a CaseStudyInput object.

        Basic usage example in python
        ```python
        import requests
        url = "https://api.tools4msp.eu/api/casestudies/{parent_lookup_casestudy__id}/inputs/{id}/tupload/
        input_file = "[path to the thumbnail image]"

        with open(input_file, 'rb') as f:
            files = {'file': f}
            r = requests.put(url, auth=('Token', TOKEN), files=files)
        ```
        """
        if 'file' not in request.data:
            raise ParseError("Empty content")

        f = request.data['file']

        obj = self.get_object()
        obj.thumbnail.save(f.name, f, save=True)
        return Response(status=status.HTTP_201_CREATED)


class CaseStudyRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows CaseStudyRuns to be viewed.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CaseStudyRunSerializer

    def get_queryset(self):
        """
        This view should return a list of all the CaseStudies
        for the currently authenticated user.
        """
        qs = CaseStudyRun.objects.all()
        # this need for avoid incompatibility with schema generator of django_filter
        if self.request is None:
            return qs
        elif not self.request.user.is_superuser:
            return qs.filter(owner=self.request.user)
        else:
            return qs
