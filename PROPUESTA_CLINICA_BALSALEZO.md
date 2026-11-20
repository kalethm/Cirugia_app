# Propuesta de implementación
## Sistema de Gestión Quirúrgica y Central de Esterilización
### Para la Clínica Balsalezo — Cartagena de Indias

**Versión del documento:** 1.0 · **Fecha:** 20 de noviembre de 2026 · **Estado:** Borrador para presentación

---

## 1. Resumen ejecutivo

La Clínica Balsalezo **no cuenta hoy con un sistema de este tipo**. Existe un prototipo funcional desarrollado como trabajo de grado ("TESIS DE PROGRAMA GESTION DE CHECKLIST"), que digitaliza tres procesos clínicos centrales y que esta propuesta busca **implementar en la clínica**:

1. **Checklist de Cirugía Segura** (OMS) con sus fases preoperatoria, firmas, intraoperatoria y postoperatoria, y generación automática del PDF.
2. **Historia clínica del paciente** con búsqueda, registro de evoluciones y un **asistente de inteligencia artificial** que responde preguntas sobre la historia usando Groq (gratuito).
3. **Central de esterilización** con inventario de sets, trazabilidad de cargas de esterilización, despacho y recepción de material, insumos, equipos, proveedores y su propio asistente de IA.
4. **Métricas y gráficas** con indicadores agregados del servicio (cirugías por mes, procedimientos frecuentes, instituciones, completitud del checklist por fase, estado de la central de esterilización) para la dirección y el personal de enfermería.

El prototipo funciona y está probado en un computador local, pero **no está implementado en la clínica**: se ejecuta en un solo equipo, los datos se perderían si ese equipo falla, no tiene HTTPS ni respaldos, y los usuarios se crean a mano en un archivo.

Esta propuesta describe (a) lo que hará el sistema una vez implementado, (b) las opciones de infraestructura para alojarlo en la clínica, y (c) los pasos, costos estimados y riesgos de la implementación.

---

## 2. Estado del prototipo (lo que se implementaría)

### 2.1 Tecnologías del prototipo

| Componente | Tecnología | Observación |
|---|---|---|
| Interfaz web | Python + Streamlit 1.67 | Se ejecuta como aplicación web; no requiere instalación en los equipos de los usuarios (solo navegador) |
| Datos | Archivos CSV en la carpeta `data/` | Simple, pero sin base de datos relacional ni control de concurrencia |
| PDF | Reportlab | Checklist de cirugía segura y logo institucional |
| Firmas digitales | `streamlit-drawable-canvas` | Firma manuscrita capturada en pantalla y guardada como imagen |
| Inteligencia artificial | Groq (`openai/gpt-oss-20b`) | Capa gratuita; la clave de API está versionada en el repositorio |
| Control de acceso | Login propio con `data/usuarios.csv` | Tres usuarios de ejemplo; la clave se guarda en texto plano |
| Repositorio | GitHub `kalethm/Cirugia_app` (privado) | Contiene código, datos de prueba y la clave de Groq |
| Despliegue actual | `streamlit run app.py` en un PC Windows (equipo del desarrollador) | No está instalado en la clínica; no hay servidor, ni HTTPS, ni proceso automático |

### 2.2 Módulos y funcionalidades a implementar

#### A. Autenticación y navegación
- Inicio de sesión con usuario y contraseña.
- Roles: **Administrador**, **Cirujano**, **Enfermería** (el control por rol hoy solo se aplica a la Central de Esterilización; el resto de secciones es visible para todos).
- Navegación superior por secciones y paneles laterales por módulo.
- Selector de tema visual: Claro, Oscuro, Verde, Azul.

#### B. Historia Clínica del Paciente
- Listado de pacientes (registro propio + pacientes que aparecen en cirugías), búsqueda por nombre o documento.
- Ficha del paciente: datos demográficos, institución, sexo, fecha de nacimiento.
- Cirugías archivadas del paciente con descarga de cada checklist en PDF.
- Historial clínico: registro de evoluciones (motivo, diagnóstico, antecedentes, observaciones) ligado a una cirugía.
- **Asistente AI** (pestaña dentro del paciente): preguntas y resumen clínico en español, basado únicamente en los datos del paciente. Indica explícitamente que no da consejos médicos.

#### C. Cirugía (Checklist OMS de Cirugía Segura)
- **Ingreso del paciente**: búsqueda por documento; si no existe, registro de datos (nombre, tipo y número de documento, institución, sexo, fecha de nacimiento, fecha de cirugía, procedimiento).
- **Checklist por fases**, con habilitación secuencial:
  - *Preoperatoria*: verificación de identidad, alergias, sitio quirúrgico, consentimiento informado, ayuno, instrumental.
  - *Firmas*: firma de auxiliar circulante, instrumentador, cirujano y anestesiólogo.
  - *Intraoperatoria*: esterilidad del campo, posición, conteo de gasas/compresas, medicación, incidencias, horarios.
  - *Postoperatoria*: control del dolor, conciencia, signos vitales, drenajes, indicaciones.
  - *Exportar PDF*: checklist final con logo y firmas.
- Validaciones que impiden avanzar si falta un dato obligatorio; alertas sonoras; borrador automático para no perder el trabajo.
- Las cirugías activas se distinguen de las **archivadas** (las que ya tienen PDF).

#### E. Métricas y Gráficas (todos los roles)
- Indicadores del periodo: cirugías del mes y del año, porcentaje de checklists completos, sets estériles vigentes, cargas en cuarentena y total de alertas de esterilización.
- Gráficas: cirugías por mes (3, 6 o 12 meses), procedimientos más frecuentes, instituciones, completitud del checklist por fase, sets por estado, cargas por resultado y por mes.
- Tablas de atención: insumos bajo mínimo o vencidos y equipos con mantenimiento próximo.
- Solo datos agregados; no muestra información de pacientes individuales.

#### D. Central de Esterilización (solo rol Administrador)
- **Panel**: indicadores (sets estériles, en proceso, despachados, cargas del día) y alertas de sets vencidos o por vencer, cargas en cuarentena, insumos bajo mínimo o vencidos, equipos con mantenimiento próximo.
- **Inventario**: sets e instrumental con código, tipo, especialidad, número de piezas, método de esterilización, tipo de empaque (con vida útil en días), estado (Sucio → En lavado → Empacado → Esterilizado → Despachado → Sucio), ubicación, carga y proveedor.
- **Cargas**: registro de cada ciclo (equipo, método, programa, temperatura, tiempo, presión, sets incluidos, operador, test Bowie-Dick, indicador químico e indicador biológico) y **liberación automática** de los sets según las reglas: rechazo por Bowie-Dick fallido, viraje incorrecto o biológico positivo; cuarentena si el biológico está pendiente o si hay implantes sin biológico negativo.
- **Despacho y recepción**: entrega de material estéril a quirófano (con ID de cirugía opcional) y devolución del material usado con verificación de conteo de piezas.
- **Insumos**: indicadores, empaques, detergentes, etc., con stock, stock mínimo, lote, vencimiento, proveedor y registro de entradas y salidas.
- **Equipos**: autoclaves, esterilizadores, lavadoras, selladoras; serial, estado, mantenimientos, validación y proveedor de mantenimiento.
- **Proveedores**: razón social, NIT, categoría, contacto, productos/servicios, activo/inactivo.
- **Edición y eliminación** de registros desde la web (solo administrador), con trazabilidad: cada fila guarda **fecha y usuario del último cambio**.
- **Asistente IA de la central**: chat que responde con todos los datos de la central y las alertas calculadas (resumen, sets por vencer, insumos a pedir, cargas pendientes, mantenimientos). Solo consulta, no modifica registros.
- **Filtros** en todas las tablas: búsqueda de texto, botones por estado con conteo, desplegables y rango de fechas.

### 2.3 Lo que falta antes de producción

| Área | Situación actual | Riesgo |
|---|---|---|
| Base de datos | Archivos CSV planos | Dos usuarios simultáneos pueden sobrescribir datos; no hay integridad referencial |
| Respaldos | Ninguno automático | Pérdida total ante falla del disco o error humano |
| Seguridad | Claves en texto plano; HTTPS no configurado; clave de Groq en el repositorio | Interceptación de credenciales y datos de pacientes |
| Roles | Solo la Central distingue roles | Cualquier usuario con sesión ve historias clínicas y puede generar PDFs |
| Pacientes | No hay formulario de "Nuevo paciente" independiente; el paciente nace al ingresar una cirugía | Difícil registrar pacientes sin cirugía programada |
| Auditoría | Solo en la Central (fecha/usuario del último cambio) | No hay historial de quién creó o modificó una cirugía o una evolución |
| Datos de prueba | Pacientes, proveedores, sets y equipos "Demo" ya cargados en el prototipo | Deben eliminarse al implementar; la clínica empezaría con datos reales desde cero |
| Reportes | Hay métricas y gráficas básicas agregadas; falta exportación (Excel/PDF) y reportes gerenciales programados | La dirección no puede sacar cifras en un informe |
| Disponibilidad | Depende de un PC encendido y de la red local | Sin plan de continuidad |

---

## 3. Propuesta de implementación y alojamiento

La clínica no tiene el sistema; hay que **instalarlo, configurarlo y ponerlo en operación**. Existen tres caminos para alojarlo. La recomendación es la **opción 1 para piloto** y la **opción 3 para producción**.

### Opción 1 — Streamlit Community Cloud (gratis)
- **Cómo:** conectar el repositorio privado de GitHub a Streamlit Cloud, pegar la clave de Groq en *Secrets*, y listo. URL tipo `clinica-balsalezo.streamlit.app`.
- **A favor:** costo cero, HTTPS incluido, se actualiza solo con cada `git push`, accesible desde cualquier navegador de la clínica.
- **En contra:**
  - La aplicación **se duerme tras ~7 días sin uso** (o tras inactividad en planes gratuitos el repositorio puede quedar en pausa); la primera visita tarda 30–60 s.
  - **El sistema de archivos es temporal**: los CSV se pierden en cada reinicio. Habría que migrar la persistencia a GitHub, Google Sheets o una base externa, lo cual implica cambios de código y no es apto para datos clínicos.
  - Sin control de quién entra más allá del login propio.
- **Veredicto:** sirve para **demostraciones y piloto con datos ficticios**. **No apto para datos reales de pacientes**.

### Opción 2 — Streamlit Community Cloud con base externa (SQLite en disco persistente no disponible; requiere cambios)
- Streamlit Cloud no ofrece disco persistente en el plan gratuito ni en el pago básico. La opción real es usar **Supabase / Neon (PostgreSQL) o Google Sheets** como almacenamiento, lo que requiere reescribir la capa de datos (`cargar`/`guardar`) y endurecer la concurrencia.
- Costo estimado: 0 USD (niveles gratuitos de Supabase/Neon) a ~25 USD/mes.
- **Veredicto:** técnicamente viable, pero es un proyecto de desarrollo adicional (2–4 semanas) y sigue sin resolver respaldos gerenciados ni SLA.

### Opción 3 — Servidor propio o VPS en la nube (RECOMENDADA para producción)
Ejecutar la aplicación en un servidor bajo control de la clínica, con HTTPS, respaldos automáticos y base de datos SQLite o PostgreSQL.

**Variantes:**

| Variante | Descripción | Costo mensual estimado (USD) | Costo mensual estimado (COP, TRM ~4.200)* |
|---|---|---|---|
| **3a. VPS en la nube** (DigitalOcean, Hetzner, AWS Lightsail, Azure VM) — 1–2 vCPU, 2 GB RAM, 40 GB SSD | Lo más común. Instalar Docker, Nginx/Caddy (HTTPS automático), Streamlit como servicio (`systemd`), SQLite o PostgreSQL, cron de respaldo a almacenamiento externo (S3/B2/Wasabi) | **12 – 25** | **50.000 – 105.000** |
| **3b. Servidor físico en la clínica** (mini PC o servidor existente) | Independiente de internet para uso local; se expone por VPN o por IP pública con HTTPS. Requiere compra de equipo (~400.000 – 900.000 COP único), consumo eléctrico y mantenimiento | **5 – 15** (electricidad + internet) | **20.000 – 65.000** |
| **3c. Híbrido** | Servidor local como principal + réplica/VPS de respaldo | 15 – 35 | 65.000 – 150.000 |

\* Tipo de cambio de referencia; ajustar con la TRM vigente. Los valores son **estimaciones de mercado** y deben cotizarse con cada proveedor.

**Costos adicionales únicos (independientes de la opción):**

| Ítem | Costo estimado |
|---|---|
| Dominio `.com.co` o `.co` (ej. `cirugiabalsalezo.com.co`) | ~60.000 – 120.000 COP/año |
| Certificado SSL | 0 (Let's Encrypt automático con Caddy/Nginx) |
| Migración y configuración inicial (instalación, HTTPS, usuarios, respaldo, capacitación) | Se cotiza aparte |
| Capacitación al personal (medio día por rol) | Se cotiza aparte |
| Trabajo de hardening previo (ver §5) | Se cotiza aparte |

**Servicios de IA:** Groq tiene nivel gratuito generoso para el volumen de una clínica (decenas de consultas al día). Si se supera, el costo es bajo (centavos por millón de tokens). Alternativas: OpenAI, Anthropic o un modelo local si la clínica exige que los datos no salgan de su red.

---

## 4. Arquitectura propuesta para la clínica (Opción 3a)

```
Usuarios (quirófano, central de esterilización, oficina)
        │  HTTPS (navegador)
        ▼
   Caddy / Nginx  ── certificado SSL automático
        │
        ▼
   Streamlit (app.py)  ── servicio systemd, 1–2 workers
        │
        ├── SQLite / PostgreSQL  (datos clínicos, checklist, esterilización)
        ├── Carpeta /objeto  (PDFs, firmas, logo)
        ├── Groq API  (asistentes IA)
        └── Respaldo diario → almacenamiento externo cifrado
```

**Decisiones recomendadas:**
- **Base de datos:** pasar de CSV a **SQLite** (cero infraestructura, suficiente para el volumen de una clínica) o **PostgreSQL** si se prevé crecer. Esto resuelve la concurrencia y permite auditoría real.
- **Respaldos:** `cron` diario con `sqlite3 .backup` o `pg_dump`, cifrado, retenido 30 días, y prueba de restauración mensual.
- **Seguridad:** contraseñas con hash (bcrypt/argon2), roles aplicados a todas las secciones, bloqueo por intentos fallidos, cabeceras de seguridad, y retiro de la clave de Groq del repositorio (moverla a variable de entorno / secretos del servidor). Rotar la clave actual porque ya está en el historial de Git.
- **Cumplimiento:** los datos de pacientes son datos personales sensibles (Ley 1581 de 2012, habeas data). Recomendado: política de tratamiento de datos, autorización de los pacientes, acceso por rol, registro de auditoría de consultas a historias clínicas, y cifrado en reposo y en tránsito. Si la clínica es IPS pública o tiene habilitación, verificar con el equipo de TIC/jurídico los requisitos de la Resolución 1995 de 1999 y del Manual de Estándares de Habilitación en lo referente a historia clínica y software.

---

## 5. Plan de implementación estimado

| Fase | Contenido | Entregable |
|---|---|---|
| **0. Preparación** | Retiro de datos "Demo" y secretos del repositorio, documentación de instalación | Repositorio limpio y documentado |
| **1. Endurecimiento** | Hash de contraseñas, roles en todas las secciones, bloqueo de intentos, HTTPS, mover clave de Groq a secretos del servidor, crear usuarios reales de la clínica | Versión segura lista para instalar |
| **2. Persistencia** | Migrar CSV → SQLite (o PostgreSQL), respaldos automáticos, prueba de restauración | Base de datos robusta |
| **3. Instalación en la clínica** | VPS o servidor local, Caddy/Nginx, servicio automático, dominio, monitoreo básico | URL productiva accesible desde la red de la clínica |
| **4. Piloto** | 2–4 semanas con un quirófano y la central de esterilización, datos reales, capacitación al personal | Acta de piloto y lista de ajustes |
| **5. Puesta en marcha** | Capacitación a todo el personal, manual de usuario, mesa de ayuda y plan de soporte | Operación en régimen |

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Pérdida de datos clínicos | Base de datos + respaldo diario cifrado + copia fuera del sitio + restauración probada |
| Fuga de información de pacientes | HTTPS, hash de claves, roles, auditoría, retiro de secretos del repo, rotación de claves |
| Dependencia del desarrollador | Repositorio documentado, manual de operación, código abierto para la clínica |
| Resistencia del personal | Piloto temprano, capacitación por rol, interfaz ya en español y con temas |
| IA con respuestas incorrectas | El asistente está limitado a consulta y cita los datos; debe presentarse al personal como apoyo, no como fuente clínica |
| Costo de la IA | Nivel gratuito de Groq suficiente para el volumen esperado; alternativa local si se requiere |

---

## 7. Recomendación final para la implementación

1. **No** usar Streamlit Community Cloud con datos reales de pacientes.
2. Usar Streamlit Community Cloud o un entorno local solo para la **demostración** a la dirección de la clínica.
3. Para la implementación real, contratar un **VPS de 2 GB RAM (~12–25 USD/mes)** o un **servidor en la clínica (~5–15 USD/mes + equipo)**, completando las fases 1 y 2 del plan antes del piloto.
4. Presupuestar la implementación como un proyecto de **4 a 8 semanas** que incluye instalación, endurecimiento de seguridad, migración de datos, capacitación y soporte inicial, con un costo de infraestructura recurrente del orden de **50.000 – 110.000 COP/mes** (sin contar mano de obra).

---

## Anexo A — Glosario
- **OMS / Lista de Verificación de Cirugía Segura:** lista de 19 ítems en tres momentos (antes de la inducción, antes de la incisión, antes de que el paciente salga del quirófano) promovida por la Organización Mundial de la Salud.
- **CSSD / Central de esterilización:** unidad encargada del procesamiento de instrumental médico.
- **Indicador químico / biológico / Bowie-Dick:** dispositivos que verifican que un ciclo de esterilización alcanzó las condiciones necesarias.
- **Groq:** plataforma de inferencia de IA de alta velocidad con nivel gratuito.

## Anexo B — Archivos clave del repositorio
- `app.py`: punto de entrada y navegación.
- `cirugia.py`: checklist de cirugía segura y PDF.
- `historia_clinica_paciente.py`: pacientes, evoluciones y asistente AI clínico.
- `esterilizacion.py`: central de esterilización y asistente AI.
- `ai_assistant.py`: cliente de Groq y prompts.
- `auth.py`: inicio de sesión.
- `temas.py`, `navegacion.py`: temas y navegación.
- `data/`: datos en CSV (pacientes, cirugías, historia clínica, esterilización, usuarios).

---

*Documento elaborado a partir del análisis del código del repositorio `Cirugia_app` (rama `main`, commit `1abcb9e`). Los costos son estimaciones de mercado a noviembre de 2026 y deben confirmarse con proveedores locales.*
*Nota: la versión de `esterilizacion.py` con auditoría de cambios y el nuevo módulo `metricas.py` aún no están confirmados en el repositorio; deben revisarse antes de cerrar la fase 0.*
