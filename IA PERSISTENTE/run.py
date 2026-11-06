"""Punto de entrada de NEXUS SYSTEM AI."""
from __future__ import annotations

import sys
import traceback

import config

LOG_FILE = config.DATA_DIR / "nexus-stdout.log"


def main() -> None:
    import uvicorn

    line = "=" * 58
    print(line)
    print("  NEXUS SYSTEM AI  -  panel: http://%s:%s" % (config.HOST, config.PORT))
    print(line)
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    # En segundo plano (pythonw) no hay consola: redirigimos la salida a un archivo.
    if sys.stdout is None or not sys.stdout.isatty():
        try:
            stream = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
            sys.stdout = stream
            sys.stderr = stream
        except OSError:
            pass

    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
