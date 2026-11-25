"""PDF report of a student's top program matches."""
import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_matches_pdf_bytes(results, weights=None):
    """
    Generate a PDF with the top 100 program matches and return as bytes
    for browser download.
    
    Args:
        results: List of match dicts with keys school, program, overall, academic, campus, social
        weights: Optional dictionary with weights {'wa': academic_weight, 'wc': campus_weight, 'wso': social_weight}
    
    Returns:
        BytesIO object containing the PDF data
    """
    # Set default weights if not provided
    if weights is None:
        weights = {'wa': 1, 'wc': 1, 'wso': 1}
    w_total = sum(float(weights.get(k, 1)) for k in ('wa', 'wc', 'wso')) or 1
    
    # Create a BytesIO buffer instead of file
    buffer = BytesIO()
    
    # Create PDF - Switch to landscape orientation
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, 
                           topMargin=30, bottomMargin=18)
    
    # Rotate the page to landscape orientation
    doc.pagesize = landscape(letter)
    
    # Take top 100 or all results if less than 100
    top_programs = results[:min(100, len(results))]
    
    styles = getSampleStyleSheet()
    
    styles['Title'].alignment = 1  # Center
    styles['Title'].spaceAfter = 12
    
    # Create a custom subtitle style with a unique name
    styles.add(ParagraphStyle(name='CustomSubtitle', 
                              parent=styles['Heading2'], 
                              alignment=1,  # Center
                              spaceAfter=10))
    
    # Create style for program name cells with wrapping
    program_style = ParagraphStyle(
        name='ProgramStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=10,
        alignment=0,  # Left alignment
    )

    university_style = ParagraphStyle(
        name='UniversityStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=10,
        alignment=0,  # Left alignment
    )
    
    # Build content
    content = []
    
    # Title
    content.append(Paragraph("UniMe: Your University Program Matches", styles['Title']))
    content.append(Spacer(1, 0.25*inch))
    
    # Summary of weights
    for label, key in (("Academics", 'wa'), ("Campus life", 'wc'), ("Social life", 'wso')):
        share = float(weights.get(key, 1)) / w_total * 100
        content.append(Paragraph(f"<b>{label} weight:</b> {share:.0f}%", styles['Normal']))
    content.append(Paragraph(f"<b>Generated:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    content.append(Spacer(1, 0.25*inch))
    
    # Top programs heading
    content.append(Paragraph(f"<b>Top {len(top_programs)} Program Matches</b>", styles['Heading2']))
    content.append(Spacer(1, 0.1*inch))
    
    # Table data with wrapping program text
    table_data = [["Rank", "University", "Program", "Academic", "Campus", "Social", "Total"]]
    
    for i, m in enumerate(top_programs):
        tot, a, c, soc = m['overall'], m['academic'], m['campus'], m['social']
        uni, prog = escape(m['school']), escape(m['program'])
        # Convert the program name to a Paragraph object for wrapping
        university_cell = Paragraph(uni, university_style)
        program_cell = Paragraph(prog, program_style)
        
        table_data.append([
            str(i+1),
            university_cell,
            program_cell,  # Using Paragraph instead of string
            f"{a:.3f}",
            f"{c:.3f}",
            f"{soc:.3f}",
            f"{tot:.3f}"
        ])
    
    # Create the table with column widths
    col_widths = [30, 110, 200, 60, 60, 60, 60]  # Adjust column widths
    table = Table(table_data, repeatRows=1, colWidths=col_widths)
    
    # Define basic style first
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Make rank column centered
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        # Make university column left-aligned
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        # Program column already left-aligned by the Paragraph style
        # Make numeric columns right-aligned
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        # Vertical alignment
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Add padding to cells
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    
    # Add alternating row backgrounds
    for row in range(1, len(table_data), 2):
        style.append(('BACKGROUND', (0, row), (-1, row), colors.lightgrey))
    
    # Add conditional formatting for high scores
    for row in range(1, len(table_data)):
        # Academic score highlighting
        try:
            if float(table_data[row][3]) > 0.7:
                style.append(('BACKGROUND', (3, row), (3, row), colors.palegreen))
        except (ValueError, TypeError):
            pass
        
        # Campus score highlighting
        try:
            if float(table_data[row][4]) > 0.7:
                style.append(('BACKGROUND', (4, row), (4, row), colors.palegreen))
        except (ValueError, TypeError):
            pass
        
        # Social score highlighting
        try:
            if float(table_data[row][5]) > 0.7:
                style.append(('BACKGROUND', (5, row), (5, row), colors.palegreen))
        except (ValueError, TypeError):
            pass
    
    table.setStyle(TableStyle(style))
    content.append(table)
    
    # Build the PDF
    doc.build(content)
    
    # Reset buffer position to the beginning
    buffer.seek(0)
    return buffer
