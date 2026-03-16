"""
Módulo de notificaciones por email para el pipeline Oldies-Tango.

Uso: send_run_notification(summary, settings)
Requiere: EMAIL_SENDER y EMAIL_PASSWORD en .env (App Password de Gmail)
  → Generar en: https://myaccount.google.com/apppasswords
"""
from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional


@dataclass
class RunSummary:
    """Resumen completo del resultado de un run del pipeline."""
    status: str                              # "success" | "error"
    run_dir: Path

    # --- Video ---
    video_title: Optional[str] = None
    video_description: Optional[str] = None  # Descripción narrativa del video
    youtube_url: Optional[str] = None
    thumbnail_path: Optional[Path] = None
    total_cost_usd: float = 0.0
    agent_costs: list[dict] = field(default_factory=list)

    # --- Música ---
    music_title: Optional[str] = None
    music_artist: Optional[str] = None
    music_source: Optional[str] = None       # "public_domain" | "ai_generated"
    image_source: Optional[str] = None       # "api" | "manual" (interno, no se muestra)

    # --- Upload (puede fallar incluso si el video se generó) ---
    upload_failed: bool = False
    upload_error: Optional[str] = None

    # --- Error de pipeline ---
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # --- Trace (timing + status por paso) ---
    trace: Optional[dict] = None

    # --- Evaluaciones (grilla de criterios por agente) ---
    evaluations: list = field(default_factory=list)


def send_run_notification(summary: RunSummary, settings) -> bool:
    """Envía notificación por email. Retorna True si se envió exitosamente."""
    notif = settings.notifications
    if not notif.enabled:
        return False

    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_PASSWORD", "")

    if not sender or not password:
        print("[notifier] EMAIL_SENDER o EMAIL_PASSWORD no configurados — saltando notificación.")
        return False

    subject = _build_subject(summary)
    body_html = _build_body_html(summary)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = notif.to_email
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(notif.smtp_host, notif.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(sender, password)
            smtp.sendmail(sender, notif.to_email, msg.as_string())
        print(f"[notifier] Email enviado a {notif.to_email}")
        return True
    except Exception as e:
        print(f"[notifier] Error al enviar email: {e}")
        return False


# ─── Construcción del email ───────────────────────────────────────────────────

def _build_subject(summary: RunSummary) -> str:
    if summary.status == "success":
        title = summary.video_title or "Video generado"
        upload_tag = " ⚠️ (upload falló)" if summary.upload_failed else ""
        return f"✅ OldiesTango — {title}{upload_tag}"
    else:
        return f"❌ OldiesTango — Pipeline falló ({summary.error_type or 'Error'})"


def _build_body_html(summary: RunSummary) -> str:
    if summary.status == "success":
        return _build_success_html(summary)
    else:
        return _build_error_html(summary)


def _build_success_html(s: RunSummary) -> str:
    # Intentar traer stats de YouTube (falla silenciosamente)
    yt_report = None
    try:
        from src.core.youtube_stats import fetch_youtube_report
        yt_report = fetch_youtube_report()
        if yt_report.error:
            yt_report = None
    except Exception:
        pass

    # ── Thumbnail embebido en base64 (redimensionado para no superar 102KB de Gmail) ──
    thumbnail_html = ""
    if s.thumbnail_path and s.thumbnail_path.exists():
        try:
            from PIL import Image
            import io
            img = Image.open(s.thumbnail_path)
            img.thumbnail((560, 315), Image.LANCZOS)  # max 560px ancho, mantiene ratio
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=72, optimize=True)
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            thumb_url = s.youtube_url or "#"
            thumbnail_html = f"""
        <a href="{thumb_url}" style="display:block;margin-bottom:20px;">
            <img src="data:image/jpeg;base64,{img_b64}"
                 style="width:100%;border-radius:6px;border:1px solid #2a2a3a;" alt="thumbnail">
        </a>"""
        except Exception:
            pass

    # ── Info del video ──
    if s.youtube_url:
        video_link = f'<a href="{s.youtube_url}" style="color:#c9a84c;">{s.youtube_url}</a>'
    else:
        video_link = '<span style="color:#888;">No subido (--upload no usado)</span>'

    music_source_label = {
        "public_domain": "Dominio público (archive.org)",
        "ai_generated": "IA generada (Suno)",
    }.get(s.music_source or "", s.music_source or "—")

    upload_warning = ""
    if s.upload_failed:
        upload_warning = f"""
        <div style="background:#2a1a00;border-left:4px solid #ffc107;padding:12px 16px;margin-bottom:20px;border-radius:4px;">
            <strong style="color:#ffc107;">⚠️ Upload a YouTube falló</strong><br>
            <code style="font-size:13px;color:#aaa;">{s.upload_error or "Error desconocido"}</code>
        </div>"""

    # ── Descripción narrativa ──
    description_section = ""
    if s.video_description:
        description_section = f"""
        <div style="margin-top:20px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #333;padding-bottom:6px;">📖 Historia</h3>
            <p style="font-size:14px;line-height:1.7;color:#d0c8b8;font-style:italic;white-space:pre-wrap;">{s.video_description}</p>
        </div>"""

    # ── Grilla de evaluaciones ──
    eval_grid_section = ""
    if s.evaluations:
        from src.core.evaluation_log import render_grid_html
        eval_grid_section = render_grid_html(s.evaluations)

    # ── Trace (timing + costo + status por paso) — reemplaza desglose de costos ──
    trace_rows = _build_trace_rows(s.trace, s.agent_costs)

    # ── Tabla financiera (costo / ingresos / profit) ──
    accumulated_cost = _calc_accumulated_cost(s.run_dir)
    profit = 0.0 - accumulated_cost  # ingresos = 0 hasta monetización
    profit_color = "#e74c3c" if profit < 0 else "#2ecc71"
    finance_section = f"""
        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #333;padding-bottom:6px;">📈 Financiero</h3>
            <table style="width:100%;font-size:14px;border-collapse:collapse;">
                <tr style="border-bottom:1px solid #1e1e30;">
                    <td style="padding:6px 8px;color:#888;">Costo este run</td>
                    <td style="padding:6px 8px;text-align:right;">USD ${s.total_cost_usd:.3f}</td>
                </tr>
                <tr style="border-bottom:1px solid #1e1e30;">
                    <td style="padding:6px 8px;color:#888;">Costo acumulado (todos los runs)</td>
                    <td style="padding:6px 8px;text-align:right;">USD ${accumulated_cost:.3f}</td>
                </tr>
                <tr style="border-bottom:1px solid #1e1e30;">
                    <td style="padding:6px 8px;color:#888;">Ingresos YouTube</td>
                    <td style="padding:6px 8px;text-align:right;color:#888;">$0.000 <span style="font-size:12px;">(sin monetización aún)</span></td>
                </tr>
                <tr style="font-weight:bold;">
                    <td style="padding:8px 8px;">Profit neto</td>
                    <td style="padding:8px 8px;text-align:right;color:{profit_color};">USD ${profit:.3f}</td>
                </tr>
            </table>
        </div>"""

    # ── Stats del canal ──
    channel_section = ""
    if yt_report and yt_report.channel:
        ch = yt_report.channel
        channel_section = f"""
        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #333;padding-bottom:6px;">📊 Canal</h3>
            <table style="width:100%;font-size:14px;">
                <tr><td style="padding:4px 8px;color:#888;">Suscriptores</td>
                    <td style="padding:4px 8px;font-weight:bold;">{ch.subscribers}</td></tr>
                <tr><td style="padding:4px 8px;color:#888;">Vistas totales</td>
                    <td style="padding:4px 8px;font-weight:bold;">{ch.total_views}</td></tr>
                <tr><td style="padding:4px 8px;color:#888;">Videos publicados</td>
                    <td style="padding:4px 8px;font-weight:bold;">{ch.video_count}</td></tr>
            </table>
        </div>"""

    # ── Últimos videos ──
    videos_section = ""
    if yt_report and yt_report.recent_videos:
        cost_by_video = _load_costs_by_video_id(s.run_dir.parent)
        rows = ""
        for v in yt_report.recent_videos:
            vid_cost = cost_by_video.get(v.video_id)
            vid_revenue = 0.0  # sin monetización aún
            if vid_cost is not None:
                vid_profit = vid_revenue - vid_cost
                profit_color = "#e74c3c" if vid_profit < 0 else "#2ecc71"
                cost_cell = f'<td style="padding:6px 8px;text-align:right;">${vid_cost:.3f}</td>'
                revenue_cell = f'<td style="padding:6px 8px;text-align:right;color:#555;">$0.000</td>'
                profit_cell = f'<td style="padding:6px 8px;text-align:right;color:{profit_color};">${vid_profit:.3f}</td>'
            else:
                cost_cell = '<td style="padding:6px 8px;text-align:right;color:#555;">—</td>'
                revenue_cell = '<td style="padding:6px 8px;text-align:right;color:#555;">—</td>'
                profit_cell = '<td style="padding:6px 8px;text-align:right;color:#555;">—</td>'
            rows += f"""
                <tr style="border-bottom:1px solid #1e1e30;">
                    <td style="padding:6px 8px;">
                        <a href="{v.url}" style="color:#c9a84c;text-decoration:none;">{v.title[:42]}{"…" if len(v.title)>42 else ""}</a>
                    </td>
                    <td style="padding:6px 8px;text-align:right;">{v.views:,}</td>
                    <td style="padding:6px 8px;text-align:right;">{v.likes:,}</td>
                    <td style="padding:6px 8px;text-align:right;">{v.comments}</td>
                    {cost_cell}{revenue_cell}{profit_cell}
                </tr>"""
        videos_section = f"""
        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #333;padding-bottom:6px;">🎬 Últimos videos</h3>
            <table style="width:100%;font-size:12px;border-collapse:collapse;">
                <thead>
                    <tr style="color:#666;font-size:11px;border-bottom:1px solid #333;">
                        <th style="padding:4px 8px;text-align:left;">Título</th>
                        <th style="padding:4px 8px;text-align:right;">Vistas</th>
                        <th style="padding:4px 8px;text-align:right;">Likes</th>
                        <th style="padding:4px 8px;text-align:right;">Coments</th>
                        <th style="padding:4px 8px;text-align:right;">Costo</th>
                        <th style="padding:4px 8px;text-align:right;">Ingresos</th>
                        <th style="padding:4px 8px;text-align:right;">Profit</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    # ── Comentarios recientes ──
    comments_section = ""
    if yt_report and yt_report.recent_comments:
        comment_items = ""
        for c in yt_report.recent_comments:
            likes_tag = f' <span style="color:#666;font-size:12px;">· {c["likes"]} ❤️</span>' if c["likes"] > 0 else ""
            comment_items += f"""
                <div style="border-left:3px solid #2a2a3a;padding:8px 12px;margin-bottom:10px;">
                    <div style="font-size:12px;color:#c9a84c;font-weight:bold;">{c["author"]}{likes_tag}</div>
                    <div style="font-size:14px;color:#ccc;margin-top:4px;">{c["text"]}</div>
                </div>"""
        latest_url = f"https://youtu.be/{yt_report.latest_video_id}" if yt_report.latest_video_id else "#"
        comments_section = f"""
        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #333;padding-bottom:6px;">
                💬 Comentarios
                <a href="{latest_url}" style="font-size:12px;font-weight:normal;color:#555;margin-left:8px;">último video →</a>
            </h3>
            {comment_items}
        </div>"""
    elif yt_report and not yt_report.error:
        comments_section = """
        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #333;padding-bottom:6px;">💬 Comentarios</h3>
            <p style="color:#666;font-size:14px;">Sin comentarios aún.</p>
        </div>"""

    yt_error_note = ""
    if yt_report is None:
        yt_error_note = '<p style="color:#555;font-size:12px;margin-top:16px;">ℹ️ Stats de YouTube no disponibles.</p>'

    # ── Alerta ContentID ──
    contentid_section = ""
    if yt_report:
        claimed = [v for v in yt_report.recent_videos if v.licensed_content]
        if claimed:
            claimed_details = _get_archive_ids_for_claimed(claimed, s.run_dir.parent)
            items_html = ""
            for c in claimed_details:
                archive_cmd = ""
                if c["archive_identifier"]:
                    archive_cmd = (
                        f'<div style="margin-top:6px;font-size:12px;color:#888;">Para blacklistear, '
                        f'corré: <code style="background:#0a0a18;padding:2px 6px;border-radius:3px;color:#ffd;">'
                        f'python -c "from src.media.audio.public_domain import add_to_blacklist; '
                        f'add_to_blacklist(\'{c["archive_identifier"]}\')"</code></div>'
                    )
                items_html += f"""
                <div style="border-left:3px solid #e74c3c;padding:8px 12px;margin-bottom:8px;background:#1a0808;border-radius:0 4px 4px 0;">
                    <a href="{c['url']}" style="color:#e74c3c;font-weight:bold;">{c['title'][:60]}</a>
                    <div style="font-size:12px;color:#888;margin-top:2px;">
                        archive.org: <code style="color:#ffd;">{c['archive_identifier'] or '(no encontrado)'}</code>
                        {f'· <a href="{c["archive_url"]}" style="color:#555;">ver en archive.org</a>' if c['archive_url'] else ''}
                    </div>
                    {archive_cmd}
                </div>"""
            contentid_section = f"""
        <div style="margin-top:24px;border:1px solid #c0392b;border-radius:6px;overflow:hidden;">
            <div style="background:#2a0a0a;padding:12px 16px;border-bottom:1px solid #c0392b;">
                <strong style="color:#e74c3c;">⚠️ ContentID detectado — {len(claimed)} video(s) reclamado(s)</strong>
                <div style="font-size:12px;color:#888;margin-top:4px;">
                    Estos videos están siendo monetizados por el claimante. No incluir en compilaciones.
                    Blacklistear el identifier para que el pipeline no lo reutilice.
                </div>
            </div>
            <div style="padding:12px 16px;">
                {items_html}
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#0a0a12;color:#e0d8c8;margin:0;padding:16px;">
<div style="max-width:600px;margin:0 auto;">

    <!-- Header -->
    <div style="background:#12122a;border-top:3px solid #c9a84c;padding:20px 24px;border-radius:6px 6px 0 0;">
        <div style="font-family:Arial,sans-serif;font-size:11px;color:#555;letter-spacing:2px;text-transform:uppercase;">Oldies Tango · Run completado</div>
        <h1 style="margin:10px 0 4px;font-size:18px;color:#e8d8a0;line-height:1.4;">{s.video_title or "—"}</h1>
        <div style="font-size:13px;color:#888;">"{s.music_title or "—"}" — {s.music_artist or "—"}
            <span style="color:#555;margin-left:6px;">· {music_source_label}</span>
        </div>
        <div style="margin-top:8px;">
            {video_link}
        </div>
    </div>

    <!-- Body -->
    <div style="background:#0f0f1e;padding:24px;border-radius:0 0 6px 6px;">

        {upload_warning}
        {thumbnail_html}
        {description_section}

        <!-- Trace del run (timing + costo + status) -->
        <div style="margin-top:24px;">
            <h3 style="font-family:Arial,sans-serif;color:#c9a84c;border-bottom:1px solid #222;padding-bottom:6px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">⚡ Trace del run</h3>
            <table style="width:100%;font-size:13px;border-collapse:collapse;font-family:Arial,sans-serif;">
                <thead>
                    <tr style="color:#555;font-size:11px;border-bottom:1px solid #222;">
                        <th style="padding:4px 8px;text-align:left;">Paso</th>
                        <th style="padding:4px 8px;text-align:left;">Modelo</th>
                        <th style="padding:4px 8px;text-align:right;">Duración</th>
                        <th style="padding:4px 8px;text-align:right;">Costo</th>
                        <th style="padding:4px 8px;text-align:center;">Estado</th>
                    </tr>
                </thead>
                <tbody>{trace_rows}</tbody>
                <tfoot>
                    <tr style="border-top:1px solid #333;font-weight:bold;">
                        <td colspan="3" style="padding:6px 8px;color:#aaa;">Total este run</td>
                        <td style="padding:6px 8px;text-align:right;color:#c9a84c;">USD ${s.total_cost_usd:.4f}</td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>
        </div>

        {eval_grid_section}
        {contentid_section}
        {finance_section}
        {channel_section}
        {videos_section}
        {comments_section}
        {yt_error_note}

    </div>
</div>
</body>
</html>"""


def _build_error_html(s: RunSummary) -> str:
    # ── Trace parcial hasta el fallo ──
    partial_total = sum(c.get("est_cost_usd", 0.0) for c in s.agent_costs)
    trace_rows = _build_trace_rows(s.trace, s.agent_costs)

    costs_section = f"""
        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #222;padding-bottom:6px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">⚡ Trace hasta el fallo</h3>
            <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <thead>
                    <tr style="color:#555;font-size:11px;border-bottom:1px solid #222;">
                        <th style="padding:4px 8px;text-align:left;">Paso</th>
                        <th style="padding:4px 8px;text-align:left;">Modelo</th>
                        <th style="padding:4px 8px;text-align:right;">Duración</th>
                        <th style="padding:4px 8px;text-align:right;">Costo</th>
                        <th style="padding:4px 8px;text-align:center;">Estado</th>
                    </tr>
                </thead>
                <tbody>{trace_rows}</tbody>
                <tfoot>
                    <tr style="border-top:1px solid #333;font-weight:bold;">
                        <td colspan="3" style="padding:6px 8px;color:#aaa;">Total parcial</td>
                        <td style="padding:6px 8px;text-align:right;color:#c9a84c;">USD ${partial_total:.4f}</td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>
        </div>"""

    # ── Separar mensaje de error del traceback ──
    error_msg = s.error_message or "Sin mensaje"
    if "\n\nTraceback" in error_msg or "\n\n" in error_msg:
        parts = error_msg.split("\n\n", 1)
        main_error = parts[0]
        tb_detail = parts[1] if len(parts) > 1 else ""
    else:
        main_error = error_msg
        tb_detail = ""

    traceback_section = ""
    if tb_detail:
        traceback_section = f"""
        <div style="margin-top:16px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #222;padding-bottom:6px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">Traceback</h3>
            <code style="font-size:12px;background:#0a0a18;padding:12px 16px;border-radius:4px;display:block;white-space:pre-wrap;color:#aaa;line-height:1.5;overflow-x:auto;">{tb_detail}</code>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#0a0a12;color:#e0d8c8;margin:0;padding:16px;">
<div style="max-width:600px;margin:0 auto;">

    <div style="background:#1a0a0a;border-top:3px solid #c0392b;padding:20px 24px;border-radius:6px 6px 0 0;">
        <div style="font-size:11px;color:#555;letter-spacing:2px;text-transform:uppercase;">Oldies Tango · Pipeline falló</div>
        <h1 style="margin:10px 0 4px;font-size:18px;color:#e74c3c;">{s.error_type or "Error desconocido"}</h1>
        <p style="margin:4px 0 0;color:#888;font-size:13px;">{s.run_dir}</p>
    </div>

    <div style="background:#0f0f1e;padding:24px;border-radius:0 0 6px 6px;">

        <h3 style="color:#c9a84c;border-bottom:1px solid #222;padding-bottom:6px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">Detalle del error</h3>
        <code style="font-size:13px;background:#0a0a18;padding:12px 16px;border-radius:4px;display:block;white-space:pre-wrap;color:#ffd;line-height:1.6;border-left:3px solid #c0392b;">{main_error}</code>

        {traceback_section}
        {costs_section}

        <div style="margin-top:24px;">
            <h3 style="color:#c9a84c;border-bottom:1px solid #222;padding-bottom:6px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">Para debuggear</h3>
            <code style="font-size:13px;background:#0a0a18;padding:10px 14px;border-radius:4px;display:block;color:#aaa;">{s.run_dir}</code>
            <p style="font-size:13px;color:#555;margin-top:8px;">Revisá el archivo <code>log.jsonl</code> en esa carpeta.</p>
        </div>

    </div>
</div>
</body>
</html>"""


def _build_trace_rows(trace: dict | None, agent_costs: list[dict]) -> str:
    """
    Genera las filas HTML de la tabla de trace.
    Si hay trace disponible, usa sus spans (con duración y status).
    Si no, cae al agent_costs legacy (sin duración).
    """
    STATUS_STYLE = {
        "ok":      ("✓", "#2ecc71"),
        "error":   ("✗", "#e74c3c"),
        "skipped": ("—", "#555555"),
    }

    if trace and trace.get("spans"):
        rows = ""
        for span in trace["spans"]:
            status = span.get("status", "ok")
            icon, color = STATUS_STYLE.get(status, ("?", "#888"))
            duration_ms = span.get("duration_ms")
            duration_str = f"{duration_ms / 1000:.2f}s" if duration_ms and status != "skipped" else "—"
            meta = span.get("metadata", {})
            model = meta.get("model", "—")
            cost = meta.get("est_cost_usd", 0.0)
            cost_str = f"${cost:.4f}" if cost else "—"

            error_detail = ""
            if status == "error" and span.get("error"):
                error_detail = f'<div style="font-size:11px;color:#e74c3c;margin-top:3px;">{span["error"]}</div>'

            row_bg = "background:#1a0808;" if status == "error" else ""
            rows += f"""
            <tr style="border-bottom:1px solid #1e1e30;{row_bg}">
                <td style="padding:5px 8px;">{span["name"]}{error_detail}</td>
                <td style="padding:5px 8px;color:#888;">{model}</td>
                <td style="padding:5px 8px;text-align:right;color:#999;">{duration_str}</td>
                <td style="padding:5px 8px;text-align:right;">{cost_str}</td>
                <td style="padding:5px 8px;text-align:center;color:{color};font-weight:bold;">{icon}</td>
            </tr>"""
        return rows

    # Fallback: agent_costs sin duración
    rows = ""
    for c in agent_costs:
        rows += f"""
        <tr style="border-bottom:1px solid #1e1e30;">
            <td style="padding:5px 8px;">{c.get("agent", "—")}</td>
            <td style="padding:5px 8px;color:#888;">{c.get("model", "—")}</td>
            <td style="padding:5px 8px;text-align:right;color:#555;">—</td>
            <td style="padding:5px 8px;text-align:right;">${c.get("est_cost_usd", 0.0):.4f}</td>
            <td style="padding:5px 8px;text-align:center;color:#2ecc71;">✓</td>
        </tr>"""
    return rows


def _calc_accumulated_cost(run_dir: Path) -> float:
    """Suma los costos de todos los runs en data/runs/."""
    total = 0.0
    runs_dir = run_dir.parent
    for costs_file in runs_dir.glob("*/costs.json"):
        try:
            data = json.loads(costs_file.read_text(encoding="utf-8"))
            total += float(data.get("total_est_usd", 0.0))
        except Exception:
            pass
    return total


def _get_archive_ids_for_claimed(claimed_videos: list, runs_dir: Path) -> list[dict]:
    """
    Para cada video reclamado por ContentID, busca el archive.org identifier
    leyendo music_result.json del run correspondiente.
    """
    result = []
    for run_path in runs_dir.glob("run-*/"):
        upload_file = run_path / "upload_result.json"
        music_file = run_path / "music_result.json"
        if not upload_file.exists():
            continue
        try:
            video_id = json.loads(upload_file.read_text(encoding="utf-8")).get("video_id", "")
            claimed_vid = next((v for v in claimed_videos if v.video_id == video_id), None)
            if not claimed_vid:
                continue
            identifier, source_url = "", ""
            if music_file.exists():
                music_data = json.loads(music_file.read_text(encoding="utf-8"))
                source_url = music_data.get("source_url", "")
                if "/details/" in source_url:
                    identifier = source_url.split("/details/")[-1].strip("/")
            result.append({
                "video_id": video_id,
                "title": claimed_vid.title,
                "url": claimed_vid.url,
                "archive_identifier": identifier,
                "archive_url": source_url,
            })
        except Exception:
            continue
    return result


def _load_costs_by_video_id(runs_dir: Path) -> dict[str, float]:
    """Crea un mapa video_id → costo_usd leyendo upload_result.json + costs.json de cada run."""
    mapping: dict[str, float] = {}
    for run_path in runs_dir.glob("run-*/"):
        upload_file = run_path / "upload_result.json"
        costs_file = run_path / "costs.json"
        if not upload_file.exists() or not costs_file.exists():
            continue
        try:
            video_id = json.loads(upload_file.read_text(encoding="utf-8")).get("video_id", "")
            cost = float(json.loads(costs_file.read_text(encoding="utf-8")).get("total_est_usd", 0.0))
            if video_id:
                mapping[video_id] = cost
        except Exception:
            pass
    return mapping
