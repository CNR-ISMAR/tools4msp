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
    FileUploadSerializer, CaseStudyRunSerializer, ThumbnailUploadSerializer
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


class CaseStudyViewSet(NestedViewSetMixin, ActionSerializerMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudies to be viewed or edited.

    retrieve:
        Return a user instance.

    list:
        Return the list of available CaseStudies.

    create:
        Add a new Case Study
        Adds a new Case Study to the server. To ad additional inputs use the following methods:
            * see [/casestudies/{casestudyId}/layers](#api-casestudies-layers-create) for adding a new Layer
            * see [/casestudies/{casestudyId}/inputs](#api-casestudies-inputs-create) from adding new input parameters or datasets

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
    permission_classes = [IsAuthenticated]
    serializer_class = CaseStudySerializer
    filterset_fields = ('cstype', 'module')

    # used by Mixin to implement multiple serializer
    action_serializers = {'list': CaseStudyListSerializer}

    def get_queryset(self):
        """
        This view should return a list of all the CaseStudies
        for the currently authenticated user.
        """
        qs = CaseStudy.objects.all()
        # this need for avoid incompatibility with schema generator of django_filter
        if self.request is None:
            return qs
        elif not self.request.user.is_superuser:
            return qs.filter(owner=self.request.user)
        else:
            return qs

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
        ]
    )
    @action(detail=True, schema=run_schema)
    def run(self, request, *args, **kwargs):
        """
        Run the module
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        selected_layers = self.request.GET.get('selected_layers')
        if selected_layers is not None:
            selected_layers = selected_layers.split(',')

        rjson = {'success': False}
        cs = self.get_object()
        csr = cs.run(selected_layers=selected_layers)
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
        Run the module
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        context = Context.objects.get(label=context_label)

        cs = self.get_object()
        cs.set_or_update_context(context_label)
        rjson = {'success': True,
                 'context' : context_label}
        return Response(rjson)

    @action(detail=True)
    def clone(self, request, *args, **kwargs):
        """
        Clone the Case Study
        :param request:
        :param args:
        :param kwargs:
        :return:
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
    API endpoint that allows CaseStudy Layers to be viewed or edited.
    """
    # def get_queryset(self):
    #    return CaseStudyLayer.objects.filter(casestudy=self.kwargs['casestudy_pk'])
    queryset = CaseStudyLayer.objects.all()
    serializer_class = CaseStudyLayerSerializer

    @action(detail=True, methods=['put'], serializer_class=FileUploadSerializer)
    @parser_classes([FileUploadParser])
    def upload(self, request, *args, **kwargs):
        """
        Upload the file
        :param request:
        :param args:
        :param kwargs:
        :return:
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
        Upload the thumbnail
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        if 'file' not in request.data:
            raise ParseError("Empty content")

        f = request.data['file']

        obj = self.get_object()
        obj.thumbnail.save(f.name, f, save=True)
        return Response(status=status.HTTP_201_CREATED)


class CaseStudyInputViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows CaseStudy Input datasets to be viewed or edited.
    """
    queryset = CaseStudyInput.objects.all()
    serializer_class = CaseStudyInputSerializer

    @action(detail=True, methods=['put'], serializer_class=FileUploadSerializer)
    @parser_classes([FileUploadParser])
    def upload(self, request, *args, **kwargs):
        """
        Upload the file
        :param request:
        :param args:
        :param kwargs:
        :return:
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
        Upload the thumbnail
        :param request:
        :param args:
        :param kwargs:
        :return:
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
