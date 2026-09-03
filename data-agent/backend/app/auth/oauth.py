from authlib.integrations.httpx_client import AsyncOAuth2Client
from app.config import settings


def get_github_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
    )


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"


async def github_exchange_code(code: str) -> dict:
    """用授权码换取 GitHub access_token 和用户信息。"""
    async with get_github_client() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data["access_token"]

        userinfo_resp = await client.get(
            GITHUB_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        user_info = userinfo_resp.json()

    return {
        "provider": "github",
        "provider_user_id": str(user_info["id"]),
        "provider_login": user_info.get("login"),
        "avatar_url": user_info.get("avatar_url"),
        "access_token": access_token,
    }


WECHAT_AUTHORIZE_URL = "https://open.weixin.qq.com/connect/qrconnect"
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"


async def wechat_exchange_code(code: str) -> dict:
    """用授权码换取微信 access_token 和用户信息。"""
    import httpx

    params = {
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        token_resp = await client.get(WECHAT_TOKEN_URL, params=params)
        token_data = token_resp.json()
        access_token = token_data["access_token"]
        openid = token_data["openid"]

        userinfo_resp = await client.get(
            WECHAT_USERINFO_URL,
            params={"access_token": access_token, "openid": openid},
        )
        user_info = userinfo_resp.json()

    return {
        "provider": "wechat",
        "provider_user_id": user_info["openid"],
        "provider_login": user_info.get("nickname"),
        "avatar_url": user_info.get("headimgurl"),
        "access_token": access_token,
    }


OAUTH_PROVIDERS = {
    "github": {
        "exchange": github_exchange_code,
        "authorize_url": GITHUB_AUTHORIZE_URL,
    },
    "wechat": {
        "exchange": wechat_exchange_code,
        "authorize_url": WECHAT_AUTHORIZE_URL,
    },
}
