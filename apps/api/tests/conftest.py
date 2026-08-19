import pytest
from sqlalchemy import create_engine, text

from app.config import settings


@pytest.fixture(autouse=True)
def prevent_real_provider_calls(monkeypatch):
    """自动化测试绝不读取开发机真实 Provider 密钥。"""
    for name in (
        "MICU_LLM_API_KEY",
        "MICU_MUSIC_LLM_API_KEY",
        "MICU_IMAGE_API_KEY",
        "DEEPSEEK_API_KEY",
        "VOLC_ACCESSKEY",
        "VOLC_SECRETKEY",
        "HUNYUAN3D_API_KEY",
        "TENCENT_SECRET_ID",
        "TENCENT_SECRET_KEY",
        "ACESTEP_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings, "micu_llm_api_key", "")
    monkeypatch.setattr(settings, "micu_music_llm_api_key", "")
    monkeypatch.setattr(settings, "micu_image_api_key", "")
    monkeypatch.setattr(settings, "hunyuan3d_api_key", "")


@pytest.fixture(autouse=True)
def remove_projects_created_by_tests():
    """测试仍使用本地数据库，但不能把临时项目留在玩家的项目列表里。"""
    engine = create_engine(settings.database_url.replace("+psycopg", "+psycopg"))
    with engine.connect() as connection:
        before = set(connection.scalars(text("select id from projects")))
    yield
    with engine.begin() as connection:
        after = set(connection.scalars(text("select id from projects")))
        created = sorted(after - before)
        if created:
            connection.execute(text("delete from projects where id = any(:ids)"), {"ids": created})
    engine.dispose()
