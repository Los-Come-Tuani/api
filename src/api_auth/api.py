from typing import TYPE_CHECKING

from dmr.routing import Router

from api_auth.controllers.account import (
    AccountCloseController,
    AccountRestoreController,
    SessionRevokeController,
)
from api_auth.controllers.csrf import CsrfController
from api_auth.controllers.google import MobileGoogleController, WebGoogleController
from api_auth.controllers.group import (
    GroupDetailController,
    GroupListAllController,
    GroupListController,
)
from api_auth.controllers.login import MobileLoginController, WebLoginController
from api_auth.controllers.logout import MobileLogoutController, WebLogoutController
from api_auth.controllers.password import (
    PasswordChangeController,
    PasswordForgotController,
    PasswordResetController,
)
from api_auth.controllers.permission import (
    PermissionDetailController,
    PermissionListAllController,
    PermissionListController,
)
from api_auth.controllers.profile import ProfileController
from api_auth.controllers.refresh import MobileRefreshController, WebRefreshController
from api_auth.controllers.register import (
    RegisterCodeController,
    RegisterController,
    RegisterVerifyController,
)
from api_auth.controllers.two_factor import (
    MobileTwoFactorController,
    TwoFactorConfirmController,
    TwoFactorController,
    TwoFactorDisableController,
    TwoFactorRecoveryController,
    TwoFactorSetupController,
    WebTwoFactorController,
)
from api_auth.controllers.user import (
    ApiUserDetailController,
    ApiUserGroupsController,
    ApiUserGroupsLinkController,
    ApiUserListAllController,
    ApiUserListController,
    ApiUserPermissionsController,
    ApiUserPermissionsLinkController,
)
from api_auth.controllers.verify import MobileVerifyController, WebVerifyController
from api_core.controllers.routers import (
    route_controllers,
    route_inferred_controller,
    route_link_controller,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

router: Final[Router] = Router(
    prefix="",
    tags=["auth"],
    urls=(
        *route_controllers(
            AccountCloseController,
            AccountRestoreController,
            ApiUserDetailController,
            ApiUserListController,
            ApiUserListAllController,
            CsrfController,
            GroupDetailController,
            GroupListController,
            GroupListAllController,
            MobileGoogleController,
            MobileLoginController,
            MobileLogoutController,
            MobileRefreshController,
            MobileTwoFactorController,
            MobileVerifyController,
            PasswordChangeController,
            PasswordForgotController,
            PasswordResetController,
            PermissionDetailController,
            PermissionListController,
            PermissionListAllController,
            ProfileController,
            RegisterCodeController,
            RegisterController,
            RegisterVerifyController,
            SessionRevokeController,
            TwoFactorConfirmController,
            TwoFactorController,
            TwoFactorDisableController,
            TwoFactorRecoveryController,
            TwoFactorSetupController,
            WebGoogleController,
            WebLoginController,
            WebLogoutController,
            WebRefreshController,
            WebTwoFactorController,
            WebVerifyController,
            prefix="auth",
        ),
        route_inferred_controller(
            ctrl=ApiUserGroupsController,
            prefix="auth",
            suffix="groups",
            tail="groups",
        ),
        route_inferred_controller(
            ctrl=ApiUserPermissionsController,
            prefix="auth",
            suffix="permissions",
            tail="permissions",
        ),
        route_link_controller(ApiUserGroupsLinkController, "auth"),
        route_link_controller(ApiUserPermissionsLinkController, "auth"),
    ),
)
