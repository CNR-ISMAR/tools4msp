from rest_framework import serializers
from rest_framework_gis.serializers import GeoModelSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput, \
    CodedLabel, DomainArea, CaseStudyRun, \
    CaseStudyRunOutputLayer, CaseStudyRunOutput


class CSChildHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    def get_url(self, obj, view_name, request, format):
        """
        Given an object, return the URL that hyperlinks to the object.
        May raise a `NoReverseMatch` if the `view_name` and `lookup_field`
        attributes are not configured to correctly match the URL conf.
        """
        # Unsaved objects will not yet have a valid URL.
        if obj.pk is None:
            return None

        k = 'parent_lookup_casestudy__id'
        pk = obj.casestudy.pk
        return self.reverse(view_name,
            kwargs={
                k: pk,
                'pk': obj.pk,
            },
            request=request,
            format=format,
        )


class DomainAreaSerializer(serializers.HyperlinkedModelSerializer):
    extent = serializers.JSONField(source="geo.extent",
                                   read_only=True)
    class Meta:
        model = DomainArea
        fields = ('url', 'label', 'extent', 'geo')


class DomainAreaListSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DomainArea
        fields = ('url', 'label',)


class CodedLabelSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CodedLabel
        fields = ('url', 'group', 'code', 'label', 'old_label')
        lookup_field = 'code'
        extra_kwargs = {
            'url': {'lookup_field': 'code'}
        }


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    class Meta:
        fields = ('file',)


class ThumbnailUploadSerializer(serializers.Serializer):
    file = serializers.ImageField()
    class Meta:
        fields = ('thumbnail',)


class CaseStudyLayerSerializer(serializers.HyperlinkedModelSerializer):
    url = CSChildHyperlinkedIdentityField(view_name='casestudylayer-detail')
    code = serializers.SlugField(source="coded_label.code",
                                       read_only=True)
    label = serializers.CharField(source="coded_label.__str__",
                                       read_only=True)

    class Meta:
        model = CaseStudyLayer
        fields = ('url',
                  'file',
                  'thumbnail',
                  'coded_label',
                  'code',
                  'label')
        read_only_fields = ('file',
                            'label')
        extra_kwargs = {
            'coded_label': {'lookup_field': 'code'}
        }


class CaseStudyInputSerializer(serializers.HyperlinkedModelSerializer):
    url = CSChildHyperlinkedIdentityField(view_name='casestudyinput-detail')
    code = serializers.SlugField(source="coded_label.code",
                                       read_only=True)
    label = serializers.CharField(source="coded_label.label",
                                       read_only=True)
    class Meta:
        model = CaseStudyInput
        fields = ('url',
                  'file',
                  'thumbnail',
                  'coded_label',
                  'code',
                  'label')
        read_only_fields = ('file',
                            'label')
        extra_kwargs = {
            'coded_label': {'lookup_field': 'code'}
        }



class CaseStudySerializer(serializers.HyperlinkedModelSerializer): #ModelSerializer):
    layers = CaseStudyLayerSerializer(many=True, read_only=True)
    inputs = CaseStudyInputSerializer(many=True, read_only=True)
    extent = serializers.JSONField(source="domain_area.extent",
                                   read_only=True)
    grid = serializers.JSONField(source="gridinfo", read_only=True)
    owner = serializers.CharField(source='owner.username',
                                  read_only=True)

    class Meta:
        model = CaseStudy
        fields = ('url',
                  'id',
                  'label',
                  'description',
                  'module',
                  'cstype',
                  'tag',
                  'resolution',
                  'extent',
                  'grid',
                  'domain_area',
                  'domain_area_terms',
                  'owner',
                  'created',
                  'updated',
                  'layers',
                  'inputs',)
        read_only_fields = ('extent', 'grid', 'owner', 'created',
                            'updated', 'layers', 'inputs')

        # write_only_fields = ('domain_area',)


class CaseStudyListSerializer(CaseStudySerializer):
    thumbnails = CaseStudyInputSerializer(many=True, read_only=True, source="get_thumbnails")
    class Meta:
        model = CaseStudy
        fields = ('url',
                  'id',
                  'label',
                  'description',
                  'module',
                  'cstype',
                  'tag',
                  'resolution',
                  'extent',
                  'owner',
                  'created',
                  'updated',
                  'thumbnails')
        read_only_fields = ('extent', 'owner''created',
                            'updated', 'layers', 'inputs')

class CaseStudyCloneSerializer(CaseStudySerializer):
    class Meta:
        model = CaseStudy
        fields = ('label',
                  'description',
                  'tag')

class CaseStudyRunInlineBaseSerializer(serializers.ModelSerializer):
    code = serializers.SlugField(source="coded_label.code",
                              read_only=True)
    label = serializers.CharField(source="coded_label.label",
                                  read_only=True)
    coded_label = serializers.HyperlinkedRelatedField(
        many=False,
        read_only=True,
        view_name='codedlabel-detail',
        lookup_field='code'
    )

    class Meta:
        fields = (# 'url',
                  'file',
                  'thumbnail',
                  'coded_label',
                  'description',
                  'code',
                  'label')
        read_only_fields = ('file',
                            'coded_label',
                            'description',
                            'label')


class CaseStudyRunOutputLayerSerializer(CaseStudyRunInlineBaseSerializer):
    class Meta(CaseStudyRunInlineBaseSerializer.Meta):
        model = CaseStudyRunOutputLayer


class CaseStudyRunOutputSerializer(CaseStudyRunInlineBaseSerializer):
    class Meta(CaseStudyRunInlineBaseSerializer.Meta):
        model = CaseStudyRunOutput


class CaseStudyRunSerializer(serializers.HyperlinkedModelSerializer): #ModelSerializer):
    # layers = CaseStudyLayerSerializer(many=True, read_only=True)
    # inputs = CaseStudyInputSerializer(many=True, read_only=True)
    # extent = serializers.JSONField(source="domain_area.extent",
    #                                read_only=True)
    outputlayers = CaseStudyRunOutputLayerSerializer(many=True, read_only=True)
    outputs = CaseStudyRunOutputSerializer(many=True, read_only=True)
    owner = serializers.CharField(source='owner.username',
                                  read_only=True)

    class Meta:
        model = CaseStudyRun
        fields = ('url',
                  'id',
                  'label',
                  'description',
                  'casestudy',
                  # 'module',
                  # 'cstype',
                  # 'resolution',
                  # 'extent',
                  # 'domain_area',
                  # 'domain_area_terms',
                  'owner',
                  'created',
                  'updated',
                  # 'layers',
                  # 'inputs',
                  'outputlayers',
                  'outputs',
                  )
        read_only_fields = (# 'extent',
                            'owner',
                            'created',
                            'updated',
                            # 'layers',
                            # 'inputs',
                            'outputlayers'
                            'outputs'
                            )
