"""Cliente para la API de DeepSeek."""
from __future__ import annotations

import httpx

from config import (DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
                    SYSTEM_PROMPT)

TIMEOUT = httpx.Timeout(90.0, connect=10.0)


class DeepSeekError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(DEEPSEEK_API_KEY)


async def chat(messages: list[dict[str, str]], *,
               temperature: float = 0.6,
               system: str | None = SYSTEM_PROMPT) -> str:
    """Envía la conversación al modelo y devuelve el texto de la respuesta."""
    if not is_configured():
        raise DeepSeekError(
            "DEEPSEEK_API_KEY no configurada. Crea un archivo .env con tu clave."
        )

    payload_messages = ([{"role": "system", "content": system}] if system else []) + messages
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": payload_messages,
        "temperature": temperature,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except httpx.HTTPError as exc:
            raise DeepSeekError(f"No se pudo conectar con DeepSeek: {exc}") from exc

    if resp.status_code != 200:
        raise DeepSeekError(
            f"DeepSeek respondió {resp.status_code}: {resp.text[:300]}"
        )

    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise DeepSeekError(f"Respuesta inesperada de DeepSeek: {resp.text[:300]}") from exc
