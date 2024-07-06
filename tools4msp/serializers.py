from rest_framework import serializers
from rest_framework_gis.serializers import GeoModelSerializer
from .models import CaseStudy, CaseStudyLayer, CaseStudyInput, \
    CodedLabel, DomainArea, CaseStudyRun, \
    CaseStudyRunOutputLayer, CaseStudyRunOutput, Context, Sensitivity, \
    Use, Pressure, Env, Weight


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

class SensitivitySerializer(serializers.ModelSerializer):
    context = serializers.SlugRelatedField(
        many=False,
        queryset = Context.objects.all(),
        slug_field="label",
        read_only=False)
    pres = serializers.SlugRelatedField(
        many=False,
        queryset = Pressure.objects.all(),
        slug_field="code",
        read_only=False)
    env = serializers.SlugRelatedField(
        many=False,
        queryset = Env.objects.all(),
        slug_field="code",
        read_only=False)
    class Meta:
        model = Sensitivity
        # fields = ('id', 'url', 'label', 'extent', 'geo')
        fields = (
            'id',
            'context', 'pres', 'env',
            'impact_level', 'recovery', 'sensitivity', 'confidence',
            'references', 'notes')

class WeightSerializer(serializers.ModelSerializer):
    context = serializers.SlugRelatedField(
        many=False,
        queryset = Context.objects.all(),
        slug_field="label",
        read_only=False)
    use = serializers.SlugRelatedField(
        many=False,
        queryset = Use.objects.all(),
        slug_field="code",
        read_only=False)
    pres = serializers.SlugRelatedField(
        many=False,
        queryset = Pressure.objects.all(),
        slug_field="code",
        read_only=False)
    class Meta:
        model = Weight
        # fields = ('id', 'url', 'label', 'extent', 'geo')
        fields = (
            'id',
            'context', 'use', 'pres',
            'weight', 'distance', 'confidence',
            'references', 'notes')

class DomainAreaSerializer(serializers.HyperlinkedModelSerializer):
    extent = serializers.JSONField(source="geo.extent",
                                   read_only=True)
    class Meta:
        model = DomainArea
        fields = ('id', 'url', 'label', 'extent', 'geo')


class DomainAreaListSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DomainArea
        fields = ('id', 'url', 'label',)


class ContextSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Context
        fields = ('url', 'label', 'description', 'reference_date')

class CodedLabelSerializer(serializers.HyperlinkedModelSerializer):
    label = serializers.SerializerMethodField()

    def get_label(self, obj):
        return '{} - {}'.format(obj.group, obj.label)
    
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
        fields = ('id',
                  'url',
                  'file',
                  'thumbnail',
                  'coded_label',
                  'code',
                  'label',
                  'description',
                  )
        read_only_fields = ('id',
                            'file',
                            'thumbnail',
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
        fields = ('id',
                  'url',
                  'file',
                  'thumbnail',
                  'coded_label',
                  'code',
                  'label',
                  'description',
                  'vizmode',
                  )
        read_only_fields = ('id',
                            'file',
                            'thumbnail',
                            'label')
        extra_kwargs = {
            'coded_label': {'lookup_field': 'code'}
        }


class IsOwnerSerializerMixin(metaclass=serializers.SerializerMetaclass):
    is_owner = serializers.SerializerMethodField(read_only=True)

    def get_is_owner(self, obj):
        request = self.context['request']
        return obj.owner == request.user

        
class CaseStudySerializer(IsOwnerSerializerMixin, serializers.HyperlinkedModelSerializer): #ModelSerializer):
    layers = CaseStudyLayerSerializer(many=True, read_only=True)
    inputs = CaseStudyInputSerializer(many=True, read_only=True)
    extent = serializers.JSONField(source="domain_area.extent",
                                   read_only=True)
    grid = serializers.JSONField(source="gridinfo", read_only=True)
    owner = serializers.CharField(source='owner.username',
                                  read_only=True)
    client_application = serializers.CharField(source='client_application.name',
                                               read_only=True)
        
    domain_area_terms = serializers.PrimaryKeyRelatedField(many=True, read_only=False, queryset=DomainArea.objects.all())


    def create(self, validated_data):
        domain_area_terms = validated_data.pop('domain_area_terms', [])
        cs = CaseStudy.objects.create(**validated_data)
        for domain_area in domain_area_terms:
            cs.domain_area_terms.add(domain_area)
        return cs

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
                  # 'domain_area_terms',
                  #TODO: stavo modificando questo
                  'domain_area_terms',
                  'owner',
                  'is_owner',
                  'client_application',
                  'visibility',
                  'created',
                  'updated',
                  'layers',
                  'inputs',)
        read_only_fields = ('extent', 'grid', 'owner', 'is_owner', 'client_application', 'created',
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
                  'is_owner',
                  'created',
                  'updated',
                  'thumbnails')
        read_only_fields = ('extent', 'owner', 'is_owner', 'created',
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
    sld = serializers.ReadOnlyField()
    
    class Meta(CaseStudyRunInlineBaseSerializer.Meta):
        model = CaseStudyRunOutputLayer
        fields = ('file','thumbnail', 'coded_label', 'description', 'code', 'label', 'sld')


class CaseStudyRunOutputSerializer(CaseStudyRunInlineBaseSerializer):
    class Meta(CaseStudyRunInlineBaseSerializer.Meta):
        model = CaseStudyRunOutput


class CaseStudyRunSerializer(IsOwnerSerializerMixin, serializers.HyperlinkedModelSerializer): #ModelSerializer):
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
        fields = ('id',
                  'url',
                  'label',
                  'description',
                  'runstatus',
                  'runerror',
                  'casestudy_id',
                  'casestudy',
                  # 'module',
                  # 'cstype',
                  # 'resolution',
                  # 'extent',
                  'domain_area',
                  # 'domain_area_terms',
                  'owner',
                  'is_owner',
                  'visibility',
                  'created',
                  'updated',
                  # 'layers',
                  # 'inputs',
                  'outputlayers',
                  'outputs',
                  )
        read_only_fields = ('id',
                            # 'extent',
                            'owner',
                            'is_owner',
                            'created',
                            'updated',
                            'runstatus',
                            'runerror',
                            'casestudy',
                            # 'layers',
                            # 'inputs',
                            'outputlayers'
                            'outputs',
                            )


class CaseStudyRunListSerializer(CaseStudySerializer):
    outputlayers = CaseStudyRunOutputLayerSerializer(many=True, read_only=True)
    outputs = CaseStudyRunOutputSerializer(many=True, read_only=True)

    class Meta:
        model = CaseStudyRun
        fields = ('id',
                  'url',
                  'label',
                  'description',
                  'visibility',
                  'runstatus',
                  'casestudy_id',
                  'casestudy',
                  'owner',
                  'is_owner',
                  'created',
                  'updated',
                  'outputlayers',
                  'outputs',
                  )
        read_only_fields = fields


class CaseStudyRunAsyncRunPostSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CaseStudyRun
        fields = ('id',
                  'label',
                  'description',
                  'casestudy_id',
                  'casestudy',
                  'domain_area',
                  )
        read_only_fields = ('id',
                            'casestudy',
                            )
