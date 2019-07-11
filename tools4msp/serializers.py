from rest_framework import serializers
from rest_framework_gis.serializers import GeoModelSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput


class CaseStudyLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseStudyLayer
        fields = ('name', 'casestudy', 'layer')


class CaseStudyInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseStudyInput
        fields = ('name',)


class CaseStudySerializer(GeoModelSerializer):
    layers = CaseStudyLayerSerializer(many=True, read_only=True)
    inputs = CaseStudyInputSerializer(many=True, read_only=True)

    class Meta:
        model = CaseStudy
        fields = ('label',
                  'description',
                  'module',
                  'cstype',
                  'resolution',
                  'domain_area',
                  'created',
                  'updated',
                  'layers',
                  'inputs')
        read_only_fields = ('created', 'updated',)