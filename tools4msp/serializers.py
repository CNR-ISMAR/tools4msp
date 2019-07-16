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



class CaseStudySerializer(serializers.ModelSerializer):
    layers = CaseStudyLayerSerializer(many=True, read_only=True)
    inputs = CaseStudyInputSerializer(many=True, read_only=True)
    # extent = serializers.JSONField(read_only=True)

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