README_CONTEXTO — Proyecto “Trabajo de Data” (Ramiro Zapaia)
Última actualización: 2026-01-08

Este documento es mi “contexto base” para cualquier chat nuevo.
Asumí que todo lo siguiente es verdadero y no inventes datos que no estén acá. Si falta algo, pedímelo.

Links:
- Web: https://ramirozapaia.com
- LinkedIn: https://linkedin.com/in/ramirozapaia
- GitHub: https://github.com/zapaia
- LeetCode: https://leetcode.com/u/zapaia

Perfil rápido:
- Argentino, 24 años.
- Vivo en Australia (Gold Coast) con Working Holiday y estoy viajando.
- Objetivo: conseguir trabajo remoto en datos (freelance / contractor / full-time remoto si encaja).
- Me adapto a husos horarios (incl. night shift si hace sentido).

Este archivo resume el contexto real que Ramiro fue contando y lo que fuimos acordando en los distintos hilos de trabajo: portfolio de datos (Power BI), landing page/CV website con Vercel/Vercel+dominio, y case study ad-hoc para Takenos (AU/NZ remesas). El objetivo es que este contexto quede siempre disponible para retomar conversaciones sin perder decisiones previas, estilo, objetivos y pendientes.

────────────────────────────────────────────────────────────
1) OBJETIVO GENERAL DE RAMIRO
────────────────────────────────────────────────────────────
- Ramiro es analista de datos con habilidades en BI.
- Quiere construir un portfolio sólido para roles BI/Reporting/Product Analyst, con proyectos:
  (a) Dashboard Power BI con dataset ds_salaries (actualizable).
  (b) Un análisis ad-hoc real (Working Holiday / remesas, caso Takenos).
  (c) Una web personal/landing page estilo CV/portfolio, con narrativa clara para reclutadores.

- Busca sostener la experiencia WH (trabajar localmente) y, a la vez, desarrollarse profesionalmente en datos con proyectos reales.

────────────────────────────────────────────────────────────
2) PROYECTO 1 — POWER BI: “Tech & Data Jobs Dashboard” (ds_salaries.csv)
────────────────────────────────────────────────────────────
Objetivo:
- Dashboard profesional en Power BI, con modelo de datos correcto (esquema estrella), limpieza, KPIs relevantes, diseño prolijo, storytelling, README en inglés para GitHub.

Enfoque del dashboard:
- Orientado a un stakeholder tipo RRHH que quiere entender cuánto pagar al próximo empleado a contratar en datos.

KPIs y filtros trabajados:
- KPI propuestos como principales:
  - Median Salary
  - % Remote ratio
- Filtros considerados necesarios:
  - Employment type (porque no se puede comparar median salary PT vs FT sin separar).
  - Region (derivada del país / continente).
  - Seniority.

Diseño/UX:
- Ramiro diseñó una front page estilo “panorama general del mercado de datos” (general market overview).
- Se trabajó con estética mate blanco/negro y se discutieron colores verde/rojo para indicadores.
- Ramiro exploró mapas, gradientes y comparó con visuales nativos de PBI (Azure Maps y estilos).
- Implementó tablas con banderas y valores; buscaba combinar bandera+nombre+valor en una misma columna como ejemplo visto (PBI nativo). 

Dimensiones:
- Dim_location: Ramiro tiene “code, country, continent”.

Estado actual:
- Dashboard terminado en versión usable para mostrar nivel real de Power BI. Publicado en su Página Web

────────────────────────────────────────────────────────────
3) Proyecto 2: LANDING PAGE / CV WEBSITE (VERCEL) — CONTEXTO Y ROADMAP
────────────────────────────────────────────────────────────
Objetivo de la web:
- Aprender V0
- Landing page tipo “scroll hacia abajo” (historia en 30 segundos).
- Dirigida a reclutadores.
- En 30 segundos deben entender:
  - quién es Ramiro,
  - qué hizo,
  - qué sabe hacer,
  - qué problemas resuelve,
  - potencial de crecimiento.
- CTA: contactar por teléfono, mail o LinkedIn.

Tecnología:
- Web con Vercel (deploy).
- Dominio: www.ramirozapaia.com
- Ramiro avanzó con v0.dev (generación) y Git/GitHub en nivel básico (solo para portfolio).
- Se trabajó metadata del sitio (title, description, iconos) y reemplazar icono v0 por uno propio (RZ).

Estado actual:
- Web terminada y publicada como landing/portfolio.
- Pendiente de agregar nuevos proyectos como el proyecto 3 y proyectos a desarrollar

────────────────────────────────────────────────────────────
4) PROYECTO 3 — CASE STUDY AD-HOC: MERCADO REMESAS WHM/STUDENTS (TAKENOS)
────────────────────────────────────────────────────────────
Contexto:
- Caso real: personas latinoamericanas en Australia con visas temporales (Working Holiday Makers y Students) necesitan enviar dinero a su país.
- Se planteó analizar oportunidad de mercado para Takenos (fintech orientada a freelancers/pagos internacionales) enfocada en remesas y features “savings-friendly”.

Estructura de análisis acordada (lógica del caso):
1) Base de usuarios:
   - Estimar población latinoamericana en Australia con visas relevantes:
     - Student visas (trabajo limitado por horas).
     - Working Holiday (trabajo más flexible).
   - Se decidió dejar afuera otras visas asumiendo que quienes planean quedarse más tiempo no envían dinero del mismo modo (supuesto de enfoque al segmento temporal).

2) Earning capacity:
   - Estimar ingresos usando salario mínimo y horas de trabajo (con escenarios).
   - Ramiro armó 3 escenarios de horas semanales trabajadas para capturar incertidumbre y justificar promedio con su experiencia viviendo la situación.

3) Hourly rate:
   - Se buscó usar el mínimo oficial para “casual” (incluye casual loading).

4) Ahorro / neto:
   - Incorporar gastos para obtener capacidad neta de ahorro.

5) Comportamiento de envío:
   - Hipótesis real: Casi el 100% eventualmente necesita sacar dinero (por salida del país; casi nadie maneja efectivo en grandes montos).
   - Competencia percibida: Binance, transferencias bancarias, Remitly, Wise

6) Modelo de negocio:
   - Estimar cómo gana Takenos y cómo gana Remitly.
   - Ramiro usó take rate ~1.2% como referencia para revenue por usuario (se discutió como supuesto).

Escenarios:
- Ramiro anualizó ingresos/ahorros asumiendo que un latino promedio está activo trabajando ~9 meses (39 semanas); el resto se va en relocalización, búsqueda de trabajo, vacaciones, etc.
- Se dolarizó el market size y se construyó un market capture (Ramiro consideró que 5% era conservador y defendió que 15% podría ser alcanzable por marketing/partnerships con influencers y comunidades).

Entregables generados:
- One pager (PDF): “One Pager Takenos.pdf”
- Case study (PDF): “Case Study.pdf”

────────────────────────────────────────────────────────────
5) REUNIÓN CON TAKENOS
────────────────────────────────────────────────────────────
Se comunico con Simon, CMO Takenos, quien le gusto el proyecto y decidió armar una reunion con Juan de Growth y Pilar de Producto.
Objetivo de Ramiro:
- Comunicar con claridad el proyecto y su valor como analista.
- Dejar puerta abierta para que lo consideren como contractor (ideal: 10/10), o al menos quede en radar/recomendación.

Enfoque acordado:
- Posicionarse como “product thinker / analista externo”, no como alguien que “busca trabajo”.
- Meta: que salgan con:
  (a) una idea que les sirva
  (b) percepción de Ramiro como activo potencial


RESULTADOS Y FOLLOW-UP
────────────────────────────────────────────────────────────
- Ramiro tuvo la reunión con CMO, líder de producto y líder de growth.
- Sensación de Ramiro:
  - Fue un buen espacio.
  - Notó que tenían poco conocimiento de algunos hábitos del mercado local (ej. Mencionar QR que en AU no se usa).
  - Ramiro pudo responder muchas preguntas.
- Takenos comentó que su intención ese año era enfocarse fuertemente en remesas.
- Al final dijeron que por el momento no buscaban a nadie, pero se guardaban el contacto.
- Juan (growth) luego le escribió pidiendo si se podía conseguir el market USD de Nueva Zelanda también.

NZ — QUÉ SE ACORDÓ Y CÓMO NO “REGALAR” TRABAJO
────────────────────────────────────────────────────────────
- Ramiro considera que repetir el análisis completo para NZ lleva tiempo y no quiere regalar ese trabajo.
- Se acordó el enfoque profesional para responder:
  - Dar un “orden de magnitud preliminar” si se puede, aclarando que no es un número cerrado.
  - Explicar que para market USD comparable hay que replicar el modelo (ingresos/gastos/escenarios) y validar rieles de pago (no asumir igual que Australia).
- Ramiro calculó preliminarmente que Sudamérica (Students + WH) en NZ podría rondar ~8000 usuarios potenciales, pero no estaba seguro del cálculo.
- Mensaje propuesto por Ramiro a Juan:
  - “Vi bases oficiales de NZ y por arriba da ~8000; es menor que Australia pero perfiles parecidos.”
  - “Si les interesa un análisis de NZ, me lleva tiempo y necesito analizar bien para no usar supuestos erróneos.”
  - “Puedo evaluarlo y pasar presupuesto con detalle de análisis y entregables.”
- Juan respondio diciendo que en las próximas semanas se decidiría que países enfocar para remesas y en caso de elegir Australia, verían como continuar conmigo.


────────────────────────────────────────────────────────────
9) PENDIENTES / PRÓXIMOS PASOS DECLARADOS POR RAMIRO
────────────────────────────────────────────────────────────

- Continuar mejorando la landing page:
  - Agregar más a Portfolio Section.
  - Agregar Takenos Project a portfolio Section.
  - Mejorar reiteración de LinkedIn en contact section
  - Poner CTA a WhatsApp

- Power BI:
  -Creación de un Dashboard plenamente de diseño grafico, con estilo visual y que sea llamativo. Lo importante es mostrar que en PBI se pueden hacer proyectos muy visuales con buena imaginación.

- Agentes de IA:
  - Objetivo: Crear un proyecto que pueda generar ingresos pasivos y a la vez me permita aprender sobre agentes de IA.
	- Idea: Agentes de IA enfocados en generar videos de YouTube y/o Podcast para Spotify con musica vibes estilo "Oldies Playing" Argentinizado
		- Ej: "1949, Sentado en el puerta de casa en una noche de verano (Oldies playing in another room, Tango) 1 hora ASMR"
  - Restricciones: No tiene que ser caro y tiene que ser sustentable, tiene que ser un proyecto enfocado en aprender agentes con todo desarrollado por IA. Si las canciones las podemos usar sin sufrir Copyright podemos usar temas viejos de Tango Argentino. Si no, generamos canciones con IA que tengan ese estilo. Miniaturas creadas con IA. Titulos creados con IA. Edición para generar el mix de x Horas con IA. Desarrollado en Python o en cualquier programa de manipulación agentes que sea ampliamente usado en el mercado (Buscamos que el proyecto sirva para luego mostrar en postulaciones, por lo que la herramienta de agentes tiene que ser de alta demanda). Iteración de creación y publicaciones con código automatico dia a dia. Al menos un video / podcast por día. Evaluar la iniciativa y acordar herramientas y costos. ChatGPT Pagado disponible. 

- To do declarados a futuro (por Ramiro):
  - Aprender Vercel mientras hace su página de portfolio.
  - Aprender Copilot en Power BI.
  - Aprender Agentes de IA.

────────────────────────────────────────────────────────────
10) NOTAS DE ESTILO Y ACUERDOS DE TRABAJO
────────────────────────────────────────────────────────────
- Ramiro prefiere comunicación natural (no guiones artificiales).
- Se acordó trabajar con:
  - respuestas fundamentadas científicamente, con búsqueda de aprendizaje pero que no sean tan extensas.
  - si aparece oportunidad, abrir la puerta con calma y criterio.

FIN.
