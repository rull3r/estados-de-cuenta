# estados-de-cuenta

Analizador, conciliador y explorador de estados de cuenta bancarios venezolanos.
Sube el PDF mensual de tu banco y obtén **todas** las operaciones, búsqueda, filtros,
estadísticas y un **peritaje de conciliación al céntimo** contra el resumen oficial.

> Herramienta no oficial, sin relación con Mercantil ni con ningún banco. No es
> asesoría financiera ni contable.

[![ci](https://github.com/rull3r/estados-de-cuenta/actions/workflows/ci.yml/badge.svg)](https://github.com/rull3r/estados-de-cuenta/actions/workflows/ci.yml)
[![license: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-ffb454.svg)](LICENSE)

## ¿Por qué existe?

Los estados de cuenta de Mercantil son PDFs generados como reportes de ancho fijo:
dos tablas por página, descripciones cortadas a mitad de palabra, columnas que cambian
de ancho entre años, secciones anexas… y, en algunos meses, **el propio banco omite
filas** que solo quedan reflejadas en el saldo.

Esta herramienta fue construida y validada contra **42 estados de cuenta reales
(2023–2026, más de 60.000 movimientos)** con una regla de oro:

> Ningún error silencioso: lo que se lee se verifica contra el resumen oficial del
> banco; lo que el banco no imprimió se detecta, se cuantifica y se reporta.

## Características

- **Lectura completa del PDF**: libro principal (`MOVIMIENTOS DE CUENTA`), anexo
  `MERCANTIL EN LINEA` y `PUNTOS DE VENTA`, reconstruyendo descripciones partidas
  entre columnas y páginas.
- **Carga por lotes**: suelta o selecciona varios PDFs a la vez; se procesan en
  cola uno por uno, con estado por archivo (al céntimo / con diferencias /
  duplicado / error) y sin bloquear la base de datos.
- **Progreso en vivo**: cada archivo muestra la etapa (abriendo PDF, leyendo
  páginas X/Y, conciliando, guardando), el porcentaje, la posición en la cola y
  el tiempo estimado restante; también al reprocesar.
- **Recuperación automática**: si el servidor se reinicia a mitad de un
  procesamiento, al arrancar reencola solo los estados pendientes; y re-subir un
  archivo que falló lo reprocesa.
- **Control de archivos**: rechaza lo que no sea PDF o no sea un estado de cuenta
  soportado, y avisa si el archivo ya fue cargado (hash).
- **Detección de operaciones repetidas**: encuentra movimientos que aparecen en
  más de un estado de cuenta (períodos solapados o repetidos del mes anterior) y
  avisa al cargar un estado cuyo período se solapa con otro.
- **Conciliación automática** en cuatro niveles: totales del resumen, saldo
  inicio/final, saldos intermedios impresos y cruce de anexos.
- **Detección de filas omitidas por el banco**: localiza el tramo de páginas y el
  monto deducido, y permite registrar un ajuste para que las estadísticas cuadren
  con el saldo oficial.
- **Búsqueda robusta** que ignora los cortes del PDF (busca «cuenta» y encuentra
  `CU ENTA`), por descripción, contraparte, referencia, teléfono, método, categoría,
  montos y fechas.
- **Estadísticas**: abonos/cargos/neto, evolución de saldo, top contrapartes,
  conceptos, métodos de pago, categorías y mayores movimientos.
- **Panel contable**: tasa de ahorro, costos bancarios (comisiones, mantenimiento
  e IGTF), ticket promedio, promedio diario, flujo diario/mensual con saldo de
  cierre, comportamiento por día de la semana, días con más gasto y dona de
  categorías. Todo respeta el filtro de período seleccionado.
- **Enriquecimiento** de cada operación: contraparte, cuenta y banco destino,
  referencia, concepto, teléfono y fecha/hora de la operación.
- **Reprocesar**: vuelve a leer un estado con el motor de extracción actualizado
  sin tener que subir el archivo otra vez (botón «reprocesar PDF»).
- **Categorías configurables** por reglas de texto.
- **Exportación a CSV** de cualquier búsqueda.
- **100 % local**: los PDFs se procesan en tu equipo y la base de datos es un
  archivo SQLite dentro de `data/`. Sin nube, sin cuentas, sin telemetría.
- **CLI** para procesar y auditar sin abrir la web.

## Inicio rápido con Docker (recomendado)

```bash
git clone https://github.com/rull3r/estados-de-cuenta.git
cd estados-de-cuenta
docker compose up -d
```

Abre <http://localhost:8000> y arrastra tu PDF. Los datos quedan en `./data/`
(respalda esa carpeta; contiene la base de datos y los PDFs subidos).

## Inicio rápido local (desarrollo)

Requiere Python 3.11+ y Node 20+.

```bash
# backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate · Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# frontend (otra terminal)
cd frontend
npm install
npm run dev
```

La web de desarrollo queda en <http://localhost:5173> y hace proxy de la API a
`http://127.0.0.1:8000`.

## Despliegue en tu red local (LAN)

Para dejar la aplicación corriendo en una computadora de la casa y verla desde
cualquier dispositivo de la red (teléfono, laptop, TV…).

### 1. Preparar la máquina

- Deja la computadora encendida y, si puedes, conectada por cable.
- Reserva su IP en el router (DHCP estático) para que la URL no cambie nunca.

### 2. Abrir el puerto y arrancar

**Windows** (PowerShell como Administrador, desde la raíz del repo):

```powershell
powershell -ExecutionPolicy Bypass -File deploy/lan-windows.ps1
```

El script abre el puerto 8000 solo para redes privadas, te muestra las URLs y
levanta el servicio. Si prefieres hacerlo a mano:

```powershell
New-NetFirewallRule -DisplayName "estados-de-cuenta" -Direction Inbound `
  -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
docker compose up -d
ipconfig   # busca "Dirección IPv4" de tu adaptador de red
```

**Linux:**

```bash
sudo ufw allow 8000/tcp        # o el firewall que uses
docker compose up -d
hostname -I                    # IP de la máquina
```

Desde cualquier equipo de la red entra a: `http://IP-DE-LA-MAQUINA:8000`

### 3. Que arranque solo al encender la máquina

El `docker-compose.yml` ya trae `restart: unless-stopped`: el contenedor vuelve
solo cada vez que el motor de Docker arranca.

**Windows con Docker Desktop**

1. Docker Desktop → **Settings → General** → activa *Start Docker Desktop when
   you sign in*.
2. Si nadie inicia sesión en esa máquina, activa el inicio de sesión automático
   (`netplwiz`) o crea una tarea programada **Al iniciar el equipo** que ejecute
   `"C:\Program Files\Docker\Docker\Docker Desktop.exe"`.
3. Listo: al encender, Docker arranca y el contenedor se levanta solo.

**Linux**

```bash
sudo systemctl enable --now docker
cd estados-de-cuenta && docker compose up -d
```

### 4. Actualizar cuando haya cambios

```bash
git pull
docker compose up -d --build
```

### Seguridad

La aplicación no tiene autenticación: está pensada para tu red privada. No la
expongas directamente a internet. Si necesitas entrar desde fuera de casa, usa
una VPN (WireGuard, Tailscale) o colócala detrás de un proxy con autenticación.
Todos los datos viven en `data/`; respaldar = copiar esa carpeta.

## Línea de comandos

```bash
cd backend
python -m app.cli parse "estado de cuenta enero.pdf" --csv enero.csv --json enero.json
python -m app.cli validate "ruta/con/mis/estados"   # matriz de conciliación
```

`parse` imprime el peritaje completo (totales del libro vs. resumen, saldos
impresos, incidencias y estado final). `validate` procesa muchos archivos y
resume cuántos cuadran al céntimo y cuáles tienen diferencias.

## Demostración sin datos reales

El repositorio incluye un generador de estados de cuenta sintéticos:

```bash
cd backend
python -m app.demo ../demo/estado-sintetico-demo.pdf
# o simula una fila que el banco no imprimió:
python -m app.demo ../demo/estado-con-fila-omitida.pdf --con-fila-omitida 123.45
```

También hay un PDF de demo ya generado en `demo/estado-sintetico-demo.pdf`.

## Cómo funciona el motor

```
PDF ─► linegrid ─► adapter del banco ─► operaciones enriquecidas ─► reconciliación
         │                │                        │                      │
   coordenadas,      secciones, anclas,      método, contraparte,    resumen oficial,
   dos columnas,     reensamblado de         referencia, concepto    saldos intermedios,
   cortes de         descripciones                                   cruce de anexos
   palabra
```

1. **`linegrid`** convierte cada página en líneas lógicas por coordenadas: detecta
   el corte entre las dos tablas, agrupa palabras por línea visual y clasifica
   montos por proximidad al borde derecho de cada columna (recalibrado en cada
   página, por eso resiste cambios de formato entre años).
2. El **adapter del banco** recorre las líneas en orden de lectura real (columna
   izquierda completa y luego derecha), reconstruye descripciones partidas a mitad
   de palabra y separa las secciones.
3. El **enriquecimiento** extrae campos estructurados con expresiones regulares.
4. La **conciliación** compara: abonos y cargos del libro contra el resumen;
   la variación neta contra saldo inicial/final; cada saldo intermedio impreso
   contra la suma calculada; y los montos de los anexos contra el libro. De la
   evolución de las diferencias entre saldos intermedios se deduce cuánto y dónde
   el banco omitió filas.

## Bancos soportados

| Banco | Estado |
| --- | --- |
| Mercantil — Cuenta Corriente (2023–2026) | ✅ activo |
| Banesco | próximamente |
| Banco de Venezuela | próximamente |
| BNC | próximamente |

### Agregar un banco nuevo

1. Implementa un adapter que cumpla `BankAdapter` en `backend/app/parsers/`.
2. Reutiliza `linegrid` y produce un `ParseResult` (mismo modelo para todos).
3. Regístralo en `get_adapters()`.
4. Agrega un PDF sintético y sus tests.

La conciliación y la web funcionan igual para cualquier adapter.

## API

Documentación interactiva en `/docs` (Swagger). Endpoints principales:

- `POST /api/statements` — subir PDF (procesa y concilia en segundo plano).
- `GET /api/statements` · `GET /api/statements/{id}` — listado y peritaje.
- `GET /api/operations` — búsqueda y filtros con paginación.
- `GET /api/stats/summary` · `GET /api/stats/biggest` — estadísticas.
- `GET /api/export.csv` — exportar la búsqueda actual.
- `POST /api/statements/{id}/adjustments` — registrar una fila omitida.
- `GET/POST/DELETE /api/rules` — reglas de categorías.
- `GET /api/health` — salud del servicio.

## Estructura

```
backend/
  app/
    parsers/      linegrid, mercantil, enriquecimiento, conciliación, modelo
    services/     importación, categorías, estadísticas
    api/          endpoints FastAPI
    cli.py        línea de comandos
    demo.py       generador de estados sintéticos
  tests/          pytest (parser, conciliación y API)
frontend/         React + Vite + TypeScript (tema CRT ámbar)
Dockerfile        build multi-etapa (frontend + backend)
docker-compose.yml
```

## Privacidad y seguridad

- Los PDFs y la base de datos viven en `data/` y **nunca** se suben a ningún
  servicio. El `.gitignore` bloquea `*.pdf` y `data/`: si colaboras, tus estados
  de cuenta no se van al repositorio.
- No hay autenticación porque está pensado para ejecutarse en tu máquina o en tu
  red privada. Si lo expones a internet, ponlo detrás de un proxy con autenticación.

## Tests

```bash
cd backend
pip install -e ".[dev]"
ruff check app tests
pytest -q
```

## Licencia

[AGPL-3.0](LICENSE). Puedes usar, estudiar, modificar y compartir esta herramienta
libremente; si la ofreces como servicio en red, debes publicar también tu versión
modificada. La licencia AGPL es requisito de PyMuPDF, el motor de lectura de PDF.
