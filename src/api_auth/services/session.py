from typing import TYPE_CHECKING

from api_auth.enums import TokenTypes
from api_exceptions.errors import UnauthorizedError

from .blocklist import (
    REVOKED_DETAIL,
    blocklist_jwt_pair,
    blocklist_jwts,
    consume_jwt,
    ensure_active_jwts,
    find_blocklisted_jtis,
)
from .jwt import (
    JwtSession,
    ParsedJwtPair,
    build_jwt_pair,
    parse_jwt,
    parse_jwt_pair,
    resolve_jwt_subject,
    try_parse_jwt,
)

if TYPE_CHECKING:
    from dmr.security.jwt.token import JWToken

    from api_auth.models import ApiUser

########################################################################################


async def close_session(access: str | None, refresh: str | None) -> None:
    await blocklist_jwt_pair(parse_jwt_pair(access, refresh))


########################################################################################


async def inspect_session(
    access: str | None,
    refresh: str | None,
) -> tuple[bool, bool]:
    pair: ParsedJwtPair = parse_jwt_pair(access, refresh)

    blocked: frozenset[str] = await find_blocklisted_jtis(pair.jtis)

    return (
        pair.access is not None and pair.access.jti not in blocked,
        pair.refresh is not None and pair.refresh.jti not in blocked,
    )


########################################################################################


async def rotate_session(access: str | None, refresh: str | None) -> JwtSession:
    refresh_token: JWToken = parse_jwt(refresh, TokenTypes.REFRESH)

    pair: ParsedJwtPair = ParsedJwtPair(
        access=try_parse_jwt(access, TokenTypes.ACCESS),
        refresh=refresh_token,
    )

    user: ApiUser = await resolve_jwt_subject(pair.subject())

    if not await consume_jwt(refresh_token, user):
        raise UnauthorizedError(detail=REVOKED_DETAIL)

    if pair.access is not None:
        await blocklist_jwts((pair.access,), user)

    return JwtSession(tokens=build_jwt_pair(user), user=user)


########################################################################################


async def verify_jwt(encoded: str | None, expected_type: str) -> None:
    await ensure_active_jwts((parse_jwt(encoded, expected_type),))
