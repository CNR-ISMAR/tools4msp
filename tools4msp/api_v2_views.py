import sys
from django.core import files
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.contrib.gis.geos import GEOSGeometry
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.schemas import AutoSchema, ManualSchema
from rest_framework.decorators import action, parser_classes
from rest_framework import serializers
from rest_framework import viewsets

import coreapi, coreschema
from tools4msp.api_views import CaseStudyViewSet as CaseStudyViewSetV1
from tools4msp.api_views import CodedLabelViewSet as CodedLabelViewSetV1
from tools4msp.api_views import CaseStudyRunViewSet as CaseStudyRunViewSetV1
from tools4msp.api_views import ContextViewSet as ContextViewSetV1
from rest_framework.authtoken.models import Token
from tools4msp.filters import CodedLabelFilter, ContextFilter
import json
from .serializers import CaseStudySerializer, CaseStudyLayerSerializer, CaseStudyInputSerializer, \
    CaseStudyListSerializer, DomainAreaSerializer, DomainAreaListSerializer, CodedLabelSerializer, \
    FileUploadSerializer, CaseStudyRunSerializer, CaseStudyRunAsyncRunPostSerializer, \
    ThumbnailUploadSerializer, CaseStudyCloneSerializer, ContextSerializer, \
    SensitivitySerializer, WeightSerializer
from .models import DomainArea, CaseStudyRun, _domain_area_to_gdf, _guess_ncells, Sensitivity, CodedLabel, Weight
import logging
logger = logging.getLogger('tools4msp.api_v2_views')


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
               'next': self.get_next_link(),
               'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })


class WeightViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    queryset = Weight.objects.all()
    serializer_class = WeightSerializer
    http_method_names = ['get', 'post', 'put', 'patch']
    permission_classes = [IsAdminUser]
    filterset_fields = ('context__label', 'pres__code', 'use__code',)


class SensitivityViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    queryset = Sensitivity.objects.all()
    serializer_class = SensitivitySerializer
    http_method_names = ['get', 'post', 'put', 'patch']
    permission_classes = [IsAdminUser]
    filterset_fields = ('context__label', 'pres__code', 'env__code',)
    
    # action_serializers = {'list': DomainAreaListSerializer}
    # filterset_fields is override by the cust get_queryset
    # filterset_fields = ('label',)

#     def get_queryset(self):
#         qs = super().get_queryset()
#         if self.request.GET.get('search'):
#             return qs.filter(label__icontains=self.request.GET.get('search'))
#         return qs
# class CodedLabelViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = CodedLabel.objects.all()
#     serializer_class = CodedLabelSerializer
#     lookup_field = 'code'


class RunPostSchema(AutoSchema):
    fields = ['selected_layers', 'runtypelevel', 'domain_area',]
    def get_manual_fields(self, path, method):
        manual_fields=[
            coreapi.Field(
                "selected_layers",
                schema=coreschema.String(description="Comma-separated list of layer codes"),
                required=False,
                location='form'
            ),
            coreapi.Field(
                "runtypelevel",
                schema=coreschema.String(description="Level of run type: 3 (default)"),
                required=False,
                location='form'
            ),
        ]
        return manual_fields


class CaseStudyViewSet(CaseStudyViewSetV1):
    pagination_class = StandardResultsSetPagination
    action_serializers = {'list': CaseStudyListSerializer,
                          'cloneupdate': CaseStudyCloneSerializer,
                          'asyncrunpost': CaseStudyRunAsyncRunPostSerializer}
    
    def get_queryset(self):
        """
        This view should return a list of all the CaseStudies
        for the currently authenticated user.
        """
        queryset = self.queryset #CaseStudy.objects.all()
        # this need for avoid incompatibility with schema generator of django_filter
        if self.request is None:
            return queryset.none()
        if self.request.GET.get('search'):
            queryset = queryset.filter(label__icontains=self.request.GET.get('search'))
        if not self.request.user.is_superuser:
            u = self.request.user
            # only one client_application for each user
            ap = u.client_applications_user.first()
            
            return queryset.filter(client_application=ap)
        else:
            return queryset
        
    def perform_create(self, serializer):
        cp = self.request.user.client_applications_user.first()
        serializer.is_valid(raise_exception=True)
        
        cs = serializer.save(owner=self.request.user, client_application=cp)
        cs.domain_area_terms.add(*serializer.validated_data.get('domain_area_terms'))
        # TODO: try to avoid double save
        cs.set_domain_area()
        ncells = cs.guess_ncells()
        if ncells > 500000:
            cs.delete()
            raise serializers.ValidationError('Too many grid cells. Please increase the resolution or change the domain area.')
        cs.save()
        from pathlib import Path
        p = Path(__file__).parent / 'static/tools4msp/img/cs_thumb_default.png'
        i = cs.inputs.create(coded_label=CodedLabel.objects.get(code="CS-THUMB"))
        f = open(p, 'rb')
        i.thumbnail.save('CS-THUMB.png', files.File(f))
        # cs.set_layer_weights()
        

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
    # TODO: remove this method after migration to asyncrunpost
    @action(detail=True, schema=run_schema)
    def asyncrun(self, request, *args, **kwargs):
        """
        [DEPRECATED: see asyncrunpost]
        Execute an analysis for the current CaseStudy according to the CaseStudy configuration. The reference to a new CaseStudyRun will be returned.
        """
        print("ààààààààààààà")
        selected_layers = self.request.GET.get('selected_layers')
        if selected_layers is not None:
            selected_layers = selected_layers.split(',')

        runtypelevel = int(self.request.GET.get('runtypelevel', 3))
        # check for valid runtypelevels
        # raise ParseError("Invalid runtypelevel parameter")

        rjson = {'success': False}
        cs = self.get_object()
        csr = cs.asyncrun(selected_layers=selected_layers, runtypelevel=runtypelevel, owner=request.user)
        if csr is not None:
            csr_serializer = CaseStudyRunSerializer(csr, context={'request': request})

            rjson['success'] = True
            rjson['run'] = csr_serializer.data['url']
            rjson['run_id'] = csr.pk
            rjson['selected_layers'] = selected_layers

        return Response(rjson)
        
    @action(detail=True, schema=RunPostSchema(), methods=["POST"])
    def asyncrunpost(self, request, *args, **kwargs):
        """
        Execute an analysis for the current CaseStudy according to the CaseStudy configuration. The reference to a new CaseStudyRun will be returned.
        """
        selected_layers = request.data.get('selected_layers')
        logger.error("##########")
        logger.error(request.data)
        if selected_layers is not None:
            selected_layers = selected_layers.split(',')

        try:
            runtypelevel = int(request.data.get('runtypelevel', 3))
        except ValueError:
            raise serializers.ValidationError('Invalid value for runtypelevel')

        domain_area = request.data.get('domain_area')
        cs = self.get_object()

        
        if domain_area is not None:
            try:
                domain_area = GEOSGeometry(json.dumps(domain_area))
                if not domain_area.geom_type in ('Polygon', 'MultiPolygon'):
                    raise serializers.ValidationError('Domain area must be a Polygon or MultiPolygon')    
            except ValueError:
                raise serializers.ValidationError('The domain area is an invalid geometry')
            i = cs.domain_area.intersection(domain_area)
            # check if itersection is a polygon
            if i.dims != 2:
                raise serializers.ValidationError("The domain area doesn't intersect the case study area or it is a null-area polygon")

        # test: cs 334
        # 43.96873313 12.24077368 44.84709823 13.46481681
        # [12.24077368, 43.96873313], [12.24077368, 44.84709823], [13.46481681, 43.96873313], [12.24077368, 43.96873313]
        # { "type": "MultiPolygon", "coordinates": [ [ [ [12.24077368, 43.96873313], [12.24077368, 44.84709823], [13.46481681, 43.96873313], [12.24077368, 43.96873313] ] ] ] }
        csr = cs.asyncrun(selected_layers=selected_layers, runtypelevel=runtypelevel, owner=request.user, domain_area=domain_area)
        if csr is not None:
            csr_serializer = CaseStudyRunSerializer(csr, context={'request': request})
            rjson = {}
            rjson['success'] = True
            rjson['run'] = csr_serializer.data['url']
            rjson['run_id'] = csr.pk
            rjson['selected_layers'] = selected_layers

        return Response(rjson)
        
class CheckAPIClient(BasePermission):
    def has_permission(self, request, view):
        try:
            return request.user.client_application_owner
        except:
            return False

    
class CreateUserAPIView(APIView):
    permission_classes = [CheckAPIClient,]
    def post(self, request):
        createuser_group, created = Group.objects.get_or_create(name='tools4msp_apiclients')
        username = request.data.get('username')
        u = User.objects.create(username=username)
        u.groups.add(createuser_group)
        client_application = request.user.client_application_owner 
        u.client_applications_user.add(client_application)
        token = Token.objects.create(user=u)
        return Response({'user': u.id, 'token': token.key})

    
class CodedLabelViewSet(CodedLabelViewSetV1):
    filterset_class = CodedLabelFilter


class CaseStudyRunViewSet(CaseStudyRunViewSetV1):
    filterset_fields = ('casestudy',)
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'head', 'patch', 'delete']
    
    def get_queryset(self):
        """
        This view should return a list of all the CaseStudies
        for the currently authenticated user.
        """
        qs = CaseStudyRun.objects.all()
        # this need for avoid incompatibility with schema generator of django_filter
        if self.request is None or self.request.user.is_superuser:
            return qs
        if self.action == 'list':
            _filter = Q(owner=self.request.user) | Q(visibility=2)
            return qs.filter(_filter)
        elif self.action == 'retrive':
            _filter = Q(owner=self.request.user) | Q(visibility__in=[1, 2])
            return qs.filter(_filter)
        else:
            return qs.filter(owner=self.request.user)


class ContextViewSet(ContextViewSetV1):
    filterset_class = ContextFilter
