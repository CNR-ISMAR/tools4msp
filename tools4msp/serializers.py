from rest_framework import serializers
from rest_framework_gis.serializers import GeoModelSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput, \
    CodedLabel


class CodedLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodedLabel
        fields = ('code',)


class CaseStudyLayerSerializer(serializers.ModelSerializer):
    coded_label = serializers.SlugField(source="coded_label.code",
                                        read_only=False)

    class Meta:
        model = CaseStudyLayer
        fields = ('coded_label',
                  'file')


class CaseStudyInputSerializer(serializers.ModelSerializer):
    coded_label = serializers.SlugField(source="coded_label.code",
                                        read_only=False)
    class Meta:
        model = CaseStudyInput
        fields = ('coded_label',
                  'file',)


class CaseStudySerializer(serializers.HyperlinkedModelSerializer): #ModelSerializer):
    layers = CaseStudyLayerSerializer(many=True, read_only=True)
    inputs = CaseStudyInputSerializer(many=True, read_only=True)
    extent = serializers.JSONField(source="domain_area.extent",
                                   read_only=True)

    class Meta:
        model = CaseStudy
        fields = ('url',
                  'id',
                  'label',
                  'description',
                  'module',
                  'cstype',
                  'resolution',
                  'extent',
                  'domain_area',
                  'created',
                  'updated',
                  'layers',
                  'inputs')
        read_only_fields = ('extent', 'created', 'updated', 'layers', 'inputs')

        # write_only_fields = ('domain_area',)


class CaseStudyListSerializer(CaseStudySerializer):
    class Meta:
        model = CaseStudy
        fields = ('url',
                  'id',
                  'label',
                  'description',
                  'module',
                  'cstype',
                  'resolution',
                  'extent',
                  'created',
                  'updated')
        read_only_fields = ('extent', 'created', 'updated', 'layers', 'inputs')
