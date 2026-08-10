from api_core.schemas.get import BaseGet

from .group import GroupInlineGet
from .permission import PermissionGet
from .user import ApiUserInlineGet

########################################################################################


class ApiUserGroupsLinkGet(BaseGet):
    api_user: ApiUserInlineGet
    group: GroupInlineGet


########################################################################################


class ApiUserPermissionsLinkGet(BaseGet):
    api_user: ApiUserInlineGet
    permission: PermissionGet
