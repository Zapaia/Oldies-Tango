# Oldies Tango

Proyecto para construir una "video factory" automatizada (agentes de IA) enfocada en contenido estilo *oldies/tango*.

## Objetivo MVP (Semana 1)
- Crear estructura base del repo.
- Crear un pipeline dummy que genere un `run` con artifacts mínimos.
- Dejar trazabilidad clara con logs.

## Cómo correr el pipeline dummy
1) Instalar dependencias:
```bash
pip install -r requirements.txt
```

2) Ejecutar el pipeline:
```bash
python -m src.pipelines.run_daily
```

Esto crea un directorio en `data/runs/` con:
- `brief.json`
- `prompt_bundle.json`

## Cómo se “conecta” todo (idea simple)
- `configs/pipeline.yaml` define duración default y rutas.
- `configs/prompts/*.md` define los prompts base de cada agente.
- `run_daily.py` carga configs/prompts y llama al **Creative Director**.
- El **Creative Director** crea el `brief.json` (por ahora, placeholder sin IA).

## Estructura base
- `configs/`: configuraciones y prompts base.
- `src/`: código del pipeline y agentes.
- `data/runs/`: artifacts por corrida.

## Próximo paso (Día 1)
1. Definir el MVP exacto (duración, formato de video, estilo visual).
2. Ejecutar el pipeline dummy y revisar artifacts.
3. Ajustar `configs/` y prompts base.
