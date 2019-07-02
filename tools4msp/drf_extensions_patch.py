from django.shortcuts import get_object_or_404


class NestedViewSetMixin:
    def initial(self, request, *args, **kwargs):
        # Before every request to this nested viewset we
        # want to resolve all the parent lookup kwargs into
        # the actual model instances.
        # We do this so that if they don't exist a 404 will
        # be raised.
        # We also cache the result on `self` so that
        # if the request is a POST, PUT or PATCH the parent
        # models can be reused in our perform_create and
        # perform_update handlers to avoid accessing the DB
        # twice.
        self.resolved_parents = self.resolve_parent_lookup_fields()
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(**self.get_parent_lookup_fields())

    def perform_create(self, serializer):
        serializer.save(**self.resolved_parents)

    def perform_update(self, serializer):
        serializer.save(**self.resolved_parents)

    def get_parent_lookup_fields(self):
        lookup_fields = {}
        for key, value in self.kwargs.items():
            # For every kwargs the view receives we want to
            # find all the keys that begin with 'parent_lookup_'
            # because that's what our 'NestedRouterMixin' registers
            # parent lookup kwargs with.
            # Then for each of the parent lookups we want to remove
            # the 'parent_lookup_' prefix and return a new dictionary
            # with only the modified parent lookup fields
            if key.startswith('parent_lookup_'):
                parent_field = key.replace('parent_lookup_', '', 1)
                lookup_fields[parent_field] = value
        return lookup_fields

    def resolve_parent_lookup_fields(self):
        parent_lookups = self.get_parent_lookup_fields()
        resolved_parents = {}
        for key, value in parent_lookups.items():
            # the lookup key can be a django ORM query string like
            # 'project__slug' so we want to split on the first '__'
            # to get the related field's name, followed by the lookup
            # string for the related model. Using the given example
            # the related field will be 'project' and the 'slug' property
            # will be the lookup on that related model
            field, lookup = key.split('__', 1)
            related_model = self.queryset.model._meta.get_field(field).related_model # pylint: disable=protected-access
            resolved_parents[field] = get_object_or_404(related_model, **{lookup: value})
        return resolved_parents