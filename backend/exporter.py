import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

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

def generate_docx(job, output_path: Path, include_timestamps: bool = False) -> Path:
    """Generates a professional Word (.docx) document for the transcript."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor

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

    # Metadata Box Table
    table = doc.add_table(rows=3, cols=2)
    table.style = 'Table Grid'
    
    meta_items = [
        ("Original File Name", job.original_filename),
        ("Audio Duration", f"{format_timestamp(job.duration_seconds or 0)} ({round(job.duration_seconds or 0, 1)} seconds)"),
        ("Model Engine", f"Whisper {job.model_size.capitalize()}"),
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
        for seg in segments:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            
            if include_timestamps:
                ts_str = f"[{format_timestamp(seg.get('start', 0))} - {format_timestamp(seg.get('end', 0))}] "
                ts_run = p.add_run(ts_str)
                ts_run.bold = True
                ts_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                ts_run.font.size = Pt(10)
            
            txt_run = p.add_run(seg.get("text", "").strip())
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
    
    # Title & Subtitle
    story.append(Paragraph("Meeting Transcript", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", meta_subtitle))
    
    # Metadata Table
    table_data = [
        [Paragraph("<b>Original File:</b>", text_style), Paragraph(job.original_filename, text_style)],
        [Paragraph("<b>Duration:</b>", text_style), Paragraph(f"{format_timestamp(job.duration_seconds or 0)} ({round(job.duration_seconds or 0, 1)}s)", text_style)],
        [Paragraph("<b>Model Size:</b>", text_style), Paragraph(f"Whisper {job.model_size.capitalize()}", text_style)],
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
        for seg in segments:
            txt_str = seg.get("text", "").strip()
            if include_timestamps:
                ts_str = f"[{format_timestamp(seg.get('start', 0))} - {format_timestamp(seg.get('end', 0))}]"
                p_content = f"<font color='#2563EB'><b>{ts_str}</b></font> {txt_str}"
            else:
                p_content = txt_str
            
            story.append(Paragraph(p_content, text_style))
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

    lines = [
        f"MEETING TRANSCRIPT - {job.original_filename}",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Duration: {format_timestamp(job.duration_seconds or 0)}",
        "=" * 60,
        ""
    ]
    
    if segments:
        for seg in segments:
            if include_timestamps:
                ts = f"[{format_timestamp(seg.get('start', 0))} - {format_timestamp(seg.get('end', 0))}]"
                lines.append(f"{ts} {seg.get('text', '').strip()}")
            else:
                lines.append(seg.get('text', '').strip())
    else:
        lines.append(job.full_text or "")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path

def generate_srt(job, output_path: Path) -> Path:
    """Generates SubRip (.srt) subtitle file."""
    segments = []
    if job.transcript_json:
        try:
            segments = json.loads(job.transcript_json)
        except Exception:
            pass

    lines = []
    for idx, seg in enumerate(segments, 1):
        start_ts = format_srt_timestamp(seg.get('start', 0))
        end_ts = format_srt_timestamp(seg.get('end', 0))
        text = seg.get('text', '').strip()
        lines.extend([
            str(idx),
            f"{start_ts} --> {end_ts}",
            text,
            ""
        ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path
