"""
"""
Alternative PDF generation using ReportLab (Windows-compatible)
This provides dynamic page sizing without WeasyPrint/GTK dependencies.
"""

import logging
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ModuleNotFoundError:
    logger.info("No pandas installation found")
    pd = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4, A3, A2
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    logger.info("ReportLab successfully imported")
except ModuleNotFoundError:
    logger.info("ReportLab not available - install with: pip install reportlab")
    REPORTLAB_AVAILABLE = False

try:
    from superset.commands.report.exceptions import ReportSchedulePdfFailedError
except ImportError:
    # For testing purposes, create a simple exception class
    class ReportSchedulePdfFailedError(Exception):
        pass


def estimate_table_width_reportlab(dataframe) -> int:
    """
    Estimate the width required for a table based on its content (ReportLab version).
    """
    if pd is None:
        raise ReportSchedulePdfFailedError("pandas is required for table width estimation")
    
    # Base width per column (characters to pixels approximation)
    base_width = 80  # pixels per column
    
    # Calculate character width based on content
    total_width = 0
    for col in dataframe.columns:
        # Get max content length in this column
        max_content_length = max(
            len(str(dataframe[col].name)),  # Column name length
            dataframe[col].astype(str).str.len().max() if len(dataframe) > 0 else 0
        )
        
        # Estimate column width (minimum 60px, maximum 200px)
        col_width = max(60, min(200, max_content_length * 8))
        total_width += col_width
    
    logger.info("Estimated table width: %d pixels for %d columns", total_width, len(dataframe.columns))
    return total_width


def build_pdf_from_dataframe_reportlab(
    dataframe,
    title: str = "Report",
    description: str = "",
    auto_resize_page: bool = True
) -> bytes:
    """
    Generate PDF from pandas DataFrame using ReportLab (Windows-compatible).
    """
    if pd is None:
        raise ReportSchedulePdfFailedError("pandas is required for DataFrame to PDF conversion")
    
    if not REPORTLAB_AVAILABLE:
        raise ReportSchedulePdfFailedError("ReportLab is required - install with: pip install reportlab")
    
    logger.info("Starting ReportLab PDF generation with auto_resize_page=%s", auto_resize_page)
    
    try:
        # Estimate table width for page size selection
        estimated_width = estimate_table_width_reportlab(dataframe)
        
        # Determine page size based on table width
        if auto_resize_page:
            if estimated_width <= 550:
                page_size = A4  # Portrait
                orientation = "A4 Portrait"
            elif estimated_width <= 750:
                page_size = (A4[1], A4[0])  # A4 Landscape
                orientation = "A4 Landscape"
            elif estimated_width <= 1050:
                page_size = A3  # Portrait
                orientation = "A3 Portrait"
            elif estimated_width <= 1400:
                page_size = (A3[1], A3[0])  # A3 Landscape
                orientation = "A3 Landscape"
            elif estimated_width <= 2000:
                page_size = (A2[1], A2[0])  # A2 Landscape
                orientation = "A2 Landscape"
            else:
                # Custom size calculation
                width_inches = max(11, estimated_width / 72)  # 72 DPI
                page_size = (width_inches * inch, 11 * inch)
                orientation = f"Custom ({width_inches:.1f}\" wide)"
        else:
            page_size = A4
            orientation = "A4 Portrait (default)"
        
        logger.info("Selected page size: %s for table width %d px", orientation, estimated_width)
        
        # Create PDF document
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=1*inch,
            bottomMargin=0.5*inch
        )
        
        # Prepare content
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkblue
        )
        story.append(Paragraph(title, title_style))
        
        # Description
        if description:
            story.append(Paragraph(description, styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Prepare table data
        # Convert DataFrame to list format for ReportLab
        data = []
        
        # Header row
        headers = ['Index'] + list(dataframe.columns)
        data.append(headers)
        
        # Data rows
        for idx, row in dataframe.iterrows():
            row_data = [str(idx)] + [str(val) for val in row.values]
            data.append(row_data)
        
        # Create table
        table = Table(data)
        
        # Apply table styling
        table_style = [
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            
            # Data rows styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]
        
        table.setStyle(TableStyle(table_style))
        story.append(table)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        pdf_bytes = buffer.read()
        
        logger.info("Successfully generated PDF with ReportLab, size: %d bytes", len(pdf_bytes))
        return pdf_bytes
        
    except Exception as ex:
        logger.error("Error in ReportLab PDF generation: %s", str(ex))
        raise ReportSchedulePdfFailedError(f"Failed generating PDF with ReportLab: {str(ex)}") from ex


# Test function
if __name__ == "__main__":
    # Quick test
    import pandas as pd
    
    # Create test data
    data = {
        'Product': ['Widget A', 'Widget B', 'Widget C'] * 5,
        'Price': [10.99, 25.50, 15.75] * 5,
        'Quantity': [100, 50, 75] * 5,
        'Total': [1099, 1275, 1181.25] * 5,
        'Category': ['Electronics', 'Home', 'Sports'] * 5,
        'Supplier': ['Supplier X', 'Supplier Y', 'Supplier Z'] * 5
    }
    df = pd.DataFrame(data)
    
    try:
        pdf_bytes = build_pdf_from_dataframe_reportlab(
            df, 
            "ReportLab Test Report", 
            "This PDF was generated using ReportLab with dynamic page sizing.",
            auto_resize_page=True
        )
        
        with open('reportlab_test.pdf', 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✓ ReportLab PDF generated successfully: {len(pdf_bytes)} bytes")
        print("✓ Saved as 'reportlab_test.pdf'")
        
    except Exception as ex:
        print(f"✗ Error: {ex}")