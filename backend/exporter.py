import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

SPEAKER_COLORS_HEX = {
    "speaker 1": "#6366F1",
    "speaker 2": "#8B5CF6",
    "speaker 3": "#10B981",
    "speaker 4": "#F59E0B",
    "speaker 5": "#EC4899",
    "speaker 6": "#06B6D4",
    "speaker 7": "#3B82F6",
    "speaker 8": "#84CC16",
    "speaker 9": "#D97706",
    "speaker 10": "#A855F7",
}

def get_speaker_color_hex(speaker_str: str) -> str:
    if not speaker_str:
        return "#6366F1"
    return SPEAKER_COLORS_HEX.get(speaker_str.lower().strip(), "#6366F1")

def get_speaker_rgb(speaker_str: str):
    from docx.shared import RGBColor
    hex_val = get_speaker_color_hex(speaker_str).lstrip("#")
    r, g, b = int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)
    return RGBColor(r, g, b)

def format_timestamp(seconds: float) -> str:
    """Formats float seconds into HH:MM:SS format."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_srt_timestamp(seconds: float) -> str:
    """Formats float seconds into SRT timestamp HH:MM:SS,mmm."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - total_seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def group_segments_by_speaker(segments: list, is_diarized: bool = False) -> list:
    """
    Groups consecutive segments spoken by the same speaker into single speaker turns.
    """
    if not segments:
        return []

    if not is_diarized:
        return [
            {
                "speaker": None,
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", "").strip(),
                "segments": [seg]
            }
            for seg in segments
        ]

    grouped_turns = []
    current_turn = None

    for seg in segments:
        spk = seg.get("speaker", None)
        text = seg.get("text", "").strip()
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)

        if current_turn is not None and current_turn["speaker"] == spk:
            if text:
                if current_turn["text"]:
                    current_turn["text"] += " " + text
                else:
                    current_turn["text"] = text
            current_turn["end"] = end
            current_turn["segments"].append(seg)
        else:
            if current_turn is not None:
                grouped_turns.append(current_turn)
            current_turn = {
                "speaker": spk,
                "start": start,
                "end": end,
                "text": text,
                "segments": [seg]
            }

    if current_turn is not None:
        grouped_turns.append(current_turn)

    return grouped_turns

def generate_docx(job, output_path: Path, include_timestamps: bool = False) -> Path:
    """Generates a professional Word (.docx) document for the transcript."""
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()
    
    # Title
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("Meeting Transcript")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
    
    # Subtitle
    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(10)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    
    doc.add_paragraph() # Spacer

    is_diarized = getattr(job, 'enable_diarization', False)

    # Metadata Box Table
    table = doc.add_table(rows=3, cols=2)
    table.style = 'Table Grid'
    
    meta_items = [
        ("Original File Name", job.original_filename),
        ("Audio Duration", f"{format_timestamp(job.duration_seconds or 0)} ({round(job.duration_seconds or 0, 1)} seconds)"),
        ("Model Engine", f"Whisper {job.model_size.capitalize()} (Diarization: {'Enabled' if is_diarized else 'Disabled'})"),
    ]
    
    for idx, (label, val) in enumerate(meta_items):
        row = table.rows[idx]
        cell_lbl, cell_val = row.cells[0], row.cells[1]
        
        lbl_run = cell_lbl.paragraphs[0].add_run(label)
        lbl_run.bold = True
        lbl_run.font.size = Pt(10)
        lbl_run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
        
        val_run = cell_val.paragraphs[0].add_run(str(val))
        val_run.font.size = Pt(10)

    doc.add_paragraph() # Spacer

    # Section Heading
    h2 = doc.add_paragraph()
    h2_run = h2.add_run("Transcript Content")
    h2_run.font.name = "Calibri"
    h2_run.font.size = Pt(16)
    h2_run.font.bold = True
    h2_run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    segments = []
    if job.transcript_json:
        try:
            segments = json.loads(job.transcript_json)
        except Exception:
            pass

    if segments:
        turns = group_segments_by_speaker(segments, is_diarized)
        for turn in turns:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            
            # Speaker Tag (ONLY if diarization was enabled and speaker exists)
            spk_val = turn.get('speaker', None)
            if is_diarized and spk_val:
                spk_run = p.add_run(f"{spk_val}: ")
                spk_run.bold = True
                spk_run.font.color.rgb = get_speaker_rgb(spk_val)
                spk_run.font.size = Pt(11)

            if include_timestamps:
                ts_str = f"[{format_timestamp(turn.get('start', 0))} - {format_timestamp(turn.get('end', 0))}] "
                ts_run = p.add_run(ts_str)
                ts_run.bold = True
                ts_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                ts_run.font.size = Pt(10)
            
            txt_run = p.add_run(turn.get("text", "").strip())
            txt_run.font.size = Pt(11)
            txt_run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
    else:
        p = doc.add_paragraph()
        p.add_run(job.full_text or "No transcript text available.")

    doc.save(str(output_path))
    return output_path

def generate_pdf(job, output_path: Path, include_timestamps: bool = False) -> Path:
    """Generates a styled PDF document for the transcript using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    
    meta_subtitle = ParagraphStyle(
        'MetaSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=15,
        spaceAfter=10
    )
    
    text_style = ParagraphStyle(
        'SegmentText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    story = []
    is_diarized = getattr(job, 'enable_diarization', False)

    # Title & Subtitle
    story.append(Paragraph("Meeting Transcript", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", meta_subtitle))
    
    # Metadata Table
    table_data = [
        [Paragraph("<b>Original File:</b>", text_style), Paragraph(job.original_filename, text_style)],
        [Paragraph("<b>Duration:</b>", text_style), Paragraph(f"{format_timestamp(job.duration_seconds or 0)} ({round(job.duration_seconds or 0, 1)}s)", text_style)],
        [Paragraph("<b>Model Engine:</b>", text_style), Paragraph(f"Whisper {job.model_size.capitalize()} (Diarization: {'Enabled' if is_diarized else 'Disabled'})", text_style)],
    ]
    
    t = Table(table_data, colWidths=[120, 380])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=15))
    
    story.append(Paragraph("Transcript Segments", h2_style))

    segments = []
    if job.transcript_json:
        try:
            segments = json.loads(job.transcript_json)
        except Exception:
            pass

    if segments:
        turns = group_segments_by_speaker(segments, is_diarized)
        for turn in turns:
            txt_str = turn.get("text", "").strip()
            spk_val = turn.get('speaker', None)
            
            p_parts = []
            if is_diarized and spk_val:
                hex_color = get_speaker_color_hex(spk_val)
                p_parts.append(f"<font color='{hex_color}'><b>{spk_val}:</b></font>")
                
            if include_timestamps:
                ts_str = f"[{format_timestamp(turn.get('start', 0))} - {format_timestamp(turn.get('end', 0))}]"
                p_parts.append(f"<font color='#2563EB'><b>{ts_str}</b></font>")
                
            p_parts.append(txt_str)
            story.append(Paragraph(" ".join(p_parts), text_style))
    else:
        story.append(Paragraph(job.full_text or "No transcript text available.", text_style))

    doc.build(story)
    return output_path

def generate_txt(job, output_path: Path, include_timestamps: bool = False) -> Path:
    """Generates a plain text file of the transcript."""
    segments = []
    if job.transcript_json:
        try:
            segments = json.loads(job.transcript_json)
        except Exception:
            pass

    is_diarized = getattr(job, 'enable_diarization', False)

    lines = [
        f"MEETING TRANSCRIPT - {job.original_filename}",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Duration: {format_timestamp(job.duration_seconds or 0)}",
        "=" * 60,
        ""
    ]
    
    if segments:
        turns = group_segments_by_speaker(segments, is_diarized)
        for turn in turns:
            parts = []
            spk = turn.get('speaker', None)
            if is_diarized and spk:
                parts.append(f"{spk}:")
            if include_timestamps:
                parts.append(f"[{format_timestamp(turn.get('start', 0))} - {format_timestamp(turn.get('end', 0))}]")
            parts.append(turn.get('text', '').strip())
            lines.append(" ".join(parts))
    else:
        lines.append(job.full_text or "")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path

def generate_srt(job, output_path: Path) -> Path:
    """Generates SubRip (.srt) subtitle file with speaker tags if diarized."""
    segments = []
    if job.transcript_json:
        try:
            segments = json.loads(job.transcript_json)
        except Exception:
            pass

    is_diarized = getattr(job, 'enable_diarization', False)

    lines = []
    for idx, seg in enumerate(segments, 1):
        start_ts = format_srt_timestamp(seg.get('start', 0))
        end_ts = format_srt_timestamp(seg.get('end', 0))
        text = seg.get('text', '').strip()
        spk = seg.get('speaker', None)
        
        caption_text = f"{spk}: {text}" if (is_diarized and spk) else text
        lines.extend([
            str(idx),
            f"{start_ts} --> {end_ts}",
            caption_text,
            ""
        ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path
