from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# Provider 仍通过 os.getenv 读取，以便测试和部署覆盖；这里只在 Backend 进程加载根目录密钥。
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    micu_llm_api_key: str = ""
    micu_music_llm_api_key: str = ""
    micu_image_api_key: str = ""
    hunyuan3d_api_key: str = ""
    database_url: str = "postgresql+psycopg://qiwen:qiwen_local@127.0.0.1:55432/qiwen"
    api_monthly_budget_cny: int = 30
    # 供应商余额页确认的当月实际支出；估算记录不能冒充真实扣费。
    confirmed_monthly_spend_cny: float = 2.4
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_chat_model: str = "deepseek-v4-flash"
    deepseek_code_model: str = "deepseek-v4-pro"
    deepseek_timeout_seconds: float = 90
    deepseek_max_retries: int = 2
    deepseek_flash_input_cny_per_million: float = 1.01
    deepseek_flash_output_cny_per_million: float = 2.02
    deepseek_pro_input_cny_per_million: float = 3.13
    deepseek_pro_output_cny_per_million: float = 6.26
    micu_base_url: str = "https://www.micuapi.ai/v1"
    micu_chat_model: str = "gpt-5.6-terra"
    micu_code_model: str = "gpt-5.6-sol"
    micu_music_model: str = "gpt-5.6-luna"
    micu_timeout_seconds: float = 120
    micu_max_retries: int = 2
    micu_chat_input_cny_per_million: float = 0
    micu_chat_output_cny_per_million: float = 0
    micu_code_input_cny_per_million: float = 0
    micu_code_output_cny_per_million: float = 0
    micu_estimated_cny_per_call: float = 0.1
    object_storage_root: str = str(PROJECT_ROOT / "storage" / "objects")

    web_public_root: str = str(PROJECT_ROOT / "apps" / "web" / "public")
    unity_project_path: str = str(PROJECT_ROOT / "unity" / "QIWEN-VerticalSlice")
    local_bridge_url: str = "http://127.0.0.1:4567"
    local_bridge_token_file: str = str(PROJECT_ROOT / "runtime" / "bridge" / "bridge-token")
    research_export_root: str = str(PROJECT_ROOT / "exports" / "research")

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


settings = Settings()
