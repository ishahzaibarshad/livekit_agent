"""Application settings with no insecure development credential fallbacks."""

from dataclasses import dataclass
import os
from typing import Mapping

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _parse_port(value: str, name: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer port") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = "sqlite:///merideth.db"
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    DEEPGRAM_API_KEY: str = ""
    ELEVEN_API_KEY: str = ""
    ELEVEN_VOICE_ID: str = "bIHbv24MWmeRgasZH58o"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_API_KEY_SID: str = ""
    TWILIO_API_KEY_SECRET: str = ""
    TWILIO_FROM_NUMBER: str = ""
    LIVEKIT_SIP_URI: str = ""
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    METRICS_PORT: int = 9090

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        return cls(
            DATABASE_URL=env.get("DATABASE_URL", "sqlite:///merideth.db"),
            LIVEKIT_URL=(env.get("LIVEKIT_URL") or "").strip(),
            LIVEKIT_API_KEY=(env.get("LIVEKIT_API_KEY") or "").strip(),
            LIVEKIT_API_SECRET=(env.get("LIVEKIT_API_SECRET") or "").strip(),
            DEEPGRAM_API_KEY=(env.get("DEEPGRAM_API_KEY") or "").strip(),
            ELEVEN_API_KEY=(env.get("ELEVEN_API_KEY") or "").strip(),
            ELEVEN_VOICE_ID=env.get("ELEVEN_VOICE_ID", "bIHbv24MWmeRgasZH58o").strip(),
            OPENAI_API_KEY=(env.get("OPENAI_API_KEY") or "").strip(),
            OPENAI_MODEL=env.get("OPENAI_MODEL", "gpt-4o-mini").strip(),
            TWILIO_ACCOUNT_SID=(env.get("TWILIO_ACCOUNT_SID") or "").strip(),
            TWILIO_AUTH_TOKEN=(env.get("TWILIO_AUTH_TOKEN") or "").strip(),
            TWILIO_API_KEY_SID=(env.get("TWILIO_API_KEY_SID") or "").strip(),
            TWILIO_API_KEY_SECRET=(env.get("TWILIO_API_KEY_SECRET") or "").strip(),
            TWILIO_FROM_NUMBER=(env.get("TWILIO_FROM_NUMBER") or "").strip(),
            LIVEKIT_SIP_URI=(env.get("LIVEKIT_SIP_URI") or "").strip(),
            DEBUG=_parse_bool(env.get("DEBUG", "false"), "DEBUG"),
            HOST=(env.get("HOST") or "127.0.0.1").strip(),
            PORT=_parse_port(env.get("PORT", "8000"), "PORT"),
            METRICS_PORT=_parse_port(env.get("METRICS_PORT", "9090"), "METRICS_PORT"),
        )


def require_livekit_credentials(settings: Settings) -> None:
    missing = [
        name for name, value in (
            ("LIVEKIT_URL", settings.LIVEKIT_URL),
            ("LIVEKIT_API_KEY", settings.LIVEKIT_API_KEY),
            ("LIVEKIT_API_SECRET", settings.LIVEKIT_API_SECRET),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Configure the required LiveKit settings: " + ", ".join(missing))


settings = Settings.from_environment()
