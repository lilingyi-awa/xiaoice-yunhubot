import toml
import pydantic

class InistanceConfig(pydantic.BaseModel):
    apikey: str
    secret: str
    prompt: str
    model: str

class AIConfig(pydantic.BaseModel):
    moonshot_key: str
    jina_key: str

class ConfigModel(pydantic.BaseModel):
    bot: dict[str, InistanceConfig]
    engine: AIConfig
    server: dict[str, str] = pydantic.Field(default={})

with open("./config.toml", "r", encoding="utf-8") as f:
    config = ConfigModel(**toml.load(f))