"""Fils des parents côté Gestion (8.8) : le personnel qui communique avec les familles
(`announcements.publish`) lit les messages des parents et répond."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.roles import ANNOUNCEMENTS_PUBLISH
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ErrorSerializer
from apps.notifications import threads
from apps.notifications.models import Message, Thread

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


class MessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "from_school", "author_name", "topic", "body", "created_at"]
        read_only_fields = fields


class ThreadSerializer(serializers.ModelSerializer):
    student = serializers.UUIDField(source="student_id")
    student_name = serializers.CharField(source="student.full_name")
    unread = serializers.SerializerMethodField(help_text="Le parent a écrit depuis votre lecture.")

    class Meta:
        model = Thread
        fields = ["id", "student", "student_name", "last_message_at", "unread"]
        read_only_fields = fields

    def get_unread(self, thread: Thread) -> bool:
        return threads.is_unread_by_school(thread)


class ThreadDetailSerializer(ThreadSerializer):
    messages = MessageSerializer(many=True)

    class Meta(ThreadSerializer.Meta):
        fields = [*ThreadSerializer.Meta.fields, "messages"]
        read_only_fields = fields


class ReplySerializer(serializers.Serializer):
    body = serializers.CharField(max_length=1500)


@extend_schema_view(
    list=extend_schema(responses={200: ThreadSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: ThreadDetailSerializer, **ERRORS}),
)
@extend_schema(tags=["parent-messages"])
class ParentThreadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Fils des parents, le plus récent d'abord ; l'ouverture d'un fil le marque lu pour l'école."""

    required_permission = ANNOUNCEMENTS_PUBLISH
    required_module = "notifications"
    serializer_class = ThreadSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Thread.all_schools.none()
        return threads.listing().prefetch_related("messages__author")

    def retrieve(self, request: Request, pk=None) -> Response:
        thread = self.get_object()
        threads.mark_read(thread, school=True)
        return Response(ThreadDetailSerializer(thread).data)

    @extend_schema(request=ReplySerializer, responses={201: MessageSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def reply(self, request: Request, pk=None) -> Response:
        """Répond au parent : il en est prévenu sur son téléphone."""
        body = ReplySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        message = threads.reply(self.get_object(), actor=request.user, **body.validated_data)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
