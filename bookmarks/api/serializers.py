from django.db.models import prefetch_related_objects
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.serializers import ListSerializer

from bookmarks.models import Bookmark, Tag, build_tag_string
from bookmarks.services.bookmarks import create_bookmark, update_bookmark
from bookmarks.services.tags import get_or_create_tag


class TagListField(serializers.ListField):
    child = serializers.CharField()


class BookmarkListSerializer(ListSerializer):
    def to_representation(self, data):
        # Prefetch nested relations to avoid n+1 queries
        prefetch_related_objects(data, 'tags')

        return super().to_representation(data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']
        read_only_fields = []


class BookmarkSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    is_mine = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Bookmark
        fields = [
            'id',
            'url',
            'title',
            'description',
            'website_title',
            'website_description',
            'web_archive_snapshot_url',
            'favicon_file',
            'is_archived',
            'unread',
            'shared',
            'is_mine',
            'owner',
            'tag_names',
            'date_added',
            'date_modified',
        ]
        read_only_fields = [
            'website_title',
            'website_description',
            'favicon_file',
            'web_archive_snapshot_url',
            'owner',
            'is_mine',
            'date_added',
            'date_modified',
        ]
        list_serializer_class = BookmarkListSerializer

    # Override optional char fields to provide default value
    title = serializers.CharField(required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    is_archived = serializers.BooleanField(required=False, default=False)
    unread = serializers.BooleanField(required=False, default=False)
    shared = serializers.BooleanField(required=False, default=False)
    # Override readonly tag_names property to allow passing a list of tag names to create/update
    tag_names = TagListField(required=False, default=[])

    def get_is_mine(self, obj):
        owner = getattr(obj, 'owner', None)
        if owner:
            return owner.id == self.context['user'].id if self.context['user'] else False
        else:
            return False

    def create(self, validated_data):
        bookmark = Bookmark()
        bookmark.url = validated_data['url']
        bookmark.title = validated_data['title']
        bookmark.description = validated_data['description']
        bookmark.is_archived = validated_data['is_archived']
        bookmark.unread = validated_data['unread']
        bookmark.shared = validated_data['shared']
        tag_string = build_tag_string(validated_data['tag_names'])
        return create_bookmark(bookmark, tag_string, self.context['user'])

    def update(self, instance: Bookmark, validated_data):
        # Update fields if they were provided in the payload
        for key in ['url', 'title', 'description', 'unread', 'shared']:
            if key in validated_data:
                setattr(instance, key, validated_data[key])

        # Use tag string from payload, or use bookmark's current tags as fallback
        tag_string = build_tag_string(instance.tag_names)
        if 'tag_names' in validated_data:
            tag_string = build_tag_string(validated_data['tag_names'])

        return update_bookmark(instance, tag_string, self.context['user'])


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'date_added']
        read_only_fields = ['date_added']

    def create(self, validated_data):
        return get_or_create_tag(validated_data['name'], self.context['user'])