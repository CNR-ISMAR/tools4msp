from rest_framework import serializers
from rest_framework_gis.serializers import GeoModelSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput


class CaseStudyLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseStudyLayer
        fields = ('name', 'casestudy')


class CaseStudyInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseStudyInput
        fields = ('name',)


class CaseStudySerializer(GeoModelSerializer):
    layers = CaseStudyLayerSerializer(many=True)
    inputs = CaseStudyInputSerializer(many=True)

    class Meta:
        model = CaseStudy
        fields = ('label',
                  'description',
                  'grid_resolution',
                  'area_of_interest',
                  'created', 'updated',
                  'layers',
                  'inputs')
        read_only_fields = ('created', 'updated')
        pass