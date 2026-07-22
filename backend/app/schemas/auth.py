from pydantic import BaseModel


class FeishuLoginConfig(BaseModel):
    app_id: str
    redirect_uri: str
    state: str
    # 后端用 urlencode 拼好的完整授权 URL，前端整页跳转到该地址。
    authorize_url: str


class FeishuCallbackIn(BaseModel):
    code: str
    state: str
