# NEXUS SYSTEM AI

MVP funcional de un asistente de IA que supervisa tu computador Windows, conversa
con DeepSeek, recuerda todo lo hablado y diagnostica problemas de forma automática.

## Qué hace

| Función | Implementación |
| --- | --- |
| Conversación con IA | API de DeepSeek (`deepseek-chat`) |
| Memoria persistente | SQLite (`data/nexus.db`) — sobrevive al cierre del programa |
| Monitor de CPU / RAM / disco | `psutil` cada 5 s |
| Detección de consumo elevado | Umbrales configurables + enfriamiento anti-ráfagas |
| Logs en tiempo real | WebSocket (`/ws`) + histórico en SQLite |
| Diagnóstico inteligente | DeepSeek analiza cada incidente y propone acciones |
| Historial de incidentes | Estados abierto/resuelto + diagnóstico guardado |
| Dashboard web | FastAPI + HTML/CSS/JS (sin build, sin dependencias de frontend) |
| Servicio en segundo plano | Tarea programada de Windows (`service.ps1`) |

## Instalación

### Opción A — Instalador automático (sin instalar Python)

```bat
instalar.bat
```

Descarga un Python portable dentro de `runtime\`, instala pip y las librerías, y
pide la clave de DeepSeek. No modifica el Python del sistema.

### Opción B — Con el Python del sistema

```powershell
cd "C:\Users\PC\Documents\IA PERSISTENTE"
python -m pip install -r requirements.txt
Copy-Item .env.example .env        # y edita DEEPSEEK_API_KEY
```

### Opción C — Docker

```bash
docker compose up -d --build
```

Ver [COMPARTIR.txt](COMPARTIR.txt) para el detalle de cada opción.

Clave de API: <https://platform.deepseek.com/api_keys>

## Ejecutar

Doble clic en `start.bat`, o:

```powershell
python run.py
```

Abre <http://127.0.0.1:8000>.

Sin `DEEPSEEK_API_KEY` el sistema arranca igualmente: monitoriza, registra logs y
crea incidentes, pero el chat y los diagnósticos avisan de que falta la clave.

## Ejecutar en segundo plano (servicio)

La forma más sencilla es con el `.bat` (evita el bloqueo de scripts de PowerShell):

```bat
service.bat install     :: registra en el arranque de Windows y arranca ahora
service.bat status
service.bat stop
service.bat start
service.bat uninstall
```

Equivalente en PowerShell, si la política de ejecución lo permite:

```powershell
powershell -ExecutionPolicy Bypass -File .\service.ps1 install
```

No requiere permisos de administrador: crea un lanzador oculto (`pythonw.exe`, sin
ventana de consola) en la carpeta Inicio del usuario. La salida se guarda en
`data/nexus-stdout.log` por si hay que diagnosticar un fallo de arranque.

## Configuración (`.env`)

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | — | Clave de la API de DeepSeek |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Modelo a usar |
| `NEXUS_HOST` / `NEXUS_PORT` | `127.0.0.1` / `8000` | Dirección del panel |
| `CPU_ALERT_THRESHOLD` | `85` | % de CPU que genera alerta |
| `RAM_ALERT_THRESHOLD` | `85` | % de RAM que genera alerta |
| `DISK_ALERT_THRESHOLD` | `90` | % de disco que genera alerta |
| `MONITOR_INTERVAL` | `5` | Segundos entre muestras |
| `ALERT_COOLDOWN` | `120` | Segundos mínimos entre alertas del mismo tipo |
| `NEXUS_DATA_DIR` | `./data` | Carpeta de la base de datos |

## API

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/status` | Estado general, agentes, métricas, memoria |
| GET | `/api/metrics` | Métricas actuales + historial + procesos |
| GET | `/api/logs` | Últimos logs |
| POST | `/api/chat` | `{message, conversation_id?}` → respuesta de la IA |
| GET | `/api/conversations` | Lista de conversaciones guardadas |
| GET | `/api/conversations/{id}` | Mensajes de una conversación |
| DELETE | `/api/conversations/{id}` | Borra una conversación |
| GET | `/api/incidents` | Historial de incidentes |
| POST | `/api/incidents/{id}/diagnose` | Diagnóstico IA bajo demanda |
| POST | `/api/incidents/{id}/resolve` | Marca el incidente como resuelto |
| POST | `/api/analyze` | Análisis IA del estado actual del equipo |
| WS | `/ws` | Logs y métricas en vivo |

## Estructura

```
config.py           configuración y umbrales
database.py         SQLite: conversaciones, mensajes, incidentes, logs
deepseek_client.py  cliente HTTP de DeepSeek
monitor.py          muestreo de psutil, alertas y resolución automática
diagnosis.py        prompts de diagnóstico
events.py           bus de eventos para WebSockets
logger.py           registro en SQLite + consola + bus
main.py             app FastAPI (API REST + WebSocket)
run.py              arranque
instalar.bat        instalador sin necesidad de Python
start.bat           ejecutar en primer plano
service.bat         servicio en segundo plano (instalar/arrancar/parar/estado)
service.ps1         lógica del servicio (lanzador oculto en el arranque)
Dockerfile          imagen autocontenida para Docker
docker-compose.yml  arranque con Docker
tools/              generación del icono y ajuste del Python portable
static/             dashboard (index.html, style.css, app.js, iconos)
runtime/            Python portable (lo crea instalar.bat)
data/nexus.db       memoria persistente (se crea sola)
data/nexus-stdout.log  salida del modo segundo plano (para diagnosticar)
```

## Compartir con otro equipo

Ver [COMPARTIR.txt](COMPARTIR.txt). Resumen: **nunca enviar `.env` ni `data\`**
(contienen tu clave y tu historial). El receptor ejecuta `instalar.bat` una vez.
