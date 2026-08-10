from django.contrib.auth.models import Group, Permission
from django.db.transaction import atomic

from api_auth.enums import ApiUserTypes

########################################################################################


@atomic
def execute() -> None:
    # ruff: disable[commented-out-code]
    # admin_only: Q = (
    #     Q(content_type__app_label__icontains="auth")
    #     | Q(content_type__app_label__icontains="pghistory")
    #     | Q(content_type__app_label__icontains="blocklist")
    #     | Q(content_type__app_label__icontains="contenttypes")
    # )

    # read_only: Q = Q(codename__icontains="view")
    # ruff: enable[commented-out-code]

    for v in ApiUserTypes.values:
        Group.objects.get_or_create(name=v)

    Group.objects.get(
        name=ApiUserTypes.ADMIN.value,
    ).permissions.add(*Permission.objects.all())
