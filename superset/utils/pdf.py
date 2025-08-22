# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import logging
from io import BytesIO
from typing import Optional

from superset.commands.report.exceptions import ReportSchedulePdfFailedError

logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ModuleNotFoundError:
    logger.info("No pandas installation found")
    pd = None
    
try:
    from PIL import Image
except ModuleNotFoundError:
    logger.info("No PIL installation found")
    
try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
    logger.info("WeasyPrint successfully imported")
except (ModuleNotFoundError, OSError) as e:
    logger.error("WeasyPrint not available: %s", str(e))
    logger.error("Multi-page PDF with dynamic sizing will not be available")
    logger.error("Please install GTK system libraries or use alternative PDF generation")
    weasyprint = None
    WEASYPRINT_AVAILABLE = False


def estimate_table_width(dataframe) -> int:
    """
    Estimate the width required for a table based on its content.
    
    :param dataframe: The pandas DataFrame to analyze
    :return: Estimated width in pixels
    """
    if pd is None:
        raise ReportSchedulePdfFailedError("pandas is required for table width estimation")
        
    if dataframe.empty:
        return 300  # Minimum width for empty tables
    
    # Base width for index column
    total_width = 80  
    
    # Calculate minimum width needed for all columns to be visible
    num_columns = len(dataframe.columns)
    
    logger.info("Estimating width for table with %d columns", num_columns)
    
    for column in dataframe.columns:
        # Column header width
        header_width = len(str(column)) * 8 + 20  # ~8px per character + padding
        
        # Sample content width (check first few rows for performance)
        sample_size = min(10, len(dataframe))
        content_widths = []
        
        for value in dataframe[column].head(sample_size):
            if pd.isna(value):
                content_widths.append(40)  # Width for empty/NA values
            else:
                # Estimate based on string length
                str_value = str(value)
                if len(str_value) > 50:  # Very long content
                    content_widths.append(300)  # Cap at reasonable width but higher than before
                else:
                    content_widths.append(len(str_value) * 8 + 16)
        
        # Use the maximum of header width and average content width
        avg_content_width = sum(content_widths) / len(content_widths) if content_widths else 60
        column_width = max(header_width, avg_content_width, 90)  # Increased minimum width
        
        # For tables with many columns, use smaller max width per column
        if num_columns > 8:
            column_width = min(column_width, 180)  # Smaller max for many columns
        elif num_columns > 5:
            column_width = min(column_width, 220)  # Medium max for moderate columns
        else:
            column_width = min(column_width, 300)  # Larger max for few columns
        
        total_width += column_width
    
    # Add some buffer for borders and spacing
    total_width += num_columns * 2  # 2px per column for borders
    
    logger.info("Estimated total width: %d pixels for %d columns", total_width, num_columns)
    return int(total_width)


def generate_table_html(
    dataframe, 
    title: str = "Report", 
    description: str = "",
    auto_resize_page: bool = True
) -> str:
    """
    Generate HTML content for a pandas DataFrame with proper CSS for PDF generation.
    
    :param dataframe: The pandas DataFrame to convert to HTML
    :param title: The title for the report
    :param description: Optional description text
    :param auto_resize_page: Whether to automatically resize page based on table width
    :return: Complete HTML document string
    """
    if pd is None:
        raise ReportSchedulePdfFailedError("pandas is required for HTML table generation")
    # Calculate estimated table width for dynamic page sizing
    estimated_table_width = estimate_table_width(dataframe)
    
    logger.info(
        "Generating PDF for table with %d columns, %d rows, estimated width: %d px",
        len(dataframe.columns),
        len(dataframe),
        estimated_table_width
    )
    
    # Convert DataFrame to HTML table with better column handling
    table_html = dataframe.to_html(
        na_rep="", 
        index=True, 
        escape=False,
        classes="data-table",
        table_id="report-table",
        max_cols=None,  # Don't limit columns
        max_rows=None   # Don't limit rows
    )
    
    # Debug: Log information about the generated table
    logger.info(
        "Generated HTML table with %d columns (including index). Table HTML length: %d characters",
        len(dataframe.columns) + 1,  # +1 for index column
        len(table_html)
    )
    
    # Debug: Check if all column names are in the HTML
    missing_columns = []
    for col in dataframe.columns:
        if str(col) not in table_html:
            missing_columns.append(col)
    
    if missing_columns:
        logger.warning("Columns missing from HTML table: %s", missing_columns)
    else:
        logger.info("All %d columns found in HTML table", len(dataframe.columns))
    
    # Determine optimal page size based on table width
    if auto_resize_page:
        if estimated_table_width <= 550:  # A4 portrait usable width
            page_size = "A4"
            page_width = "210mm"
            page_height = "297mm"
            margin = "2cm 1.5cm"
            orientation = "portrait"
        elif estimated_table_width <= 750:  # A4 landscape usable width
            page_size = "A4 landscape"
            page_width = "297mm"
            page_height = "210mm"
            margin = "1.5cm 2cm"
            orientation = "landscape"
        elif estimated_table_width <= 1050:  # A3 portrait usable width
            page_size = "A3"
            page_width = "297mm"
            page_height = "420mm"
            margin = "2cm 1.5cm"
            orientation = "portrait"
        elif estimated_table_width <= 1400:  # A3 landscape usable width
            page_size = "A3 landscape"
            page_width = "420mm"
            page_height = "297mm"
            margin = "1.5cm 2cm"
            orientation = "landscape"
        elif estimated_table_width <= 2000:  # A2 landscape usable width
            page_size = "A2 landscape"
            page_width = "594mm"
            page_height = "420mm"
            margin = "2cm 2.5cm"
            orientation = "landscape"
        else:
            # For very wide tables, calculate custom size
            # Convert pixels to mm (roughly 3.78 pixels per mm at 96 DPI)
            table_width_mm = int(estimated_table_width / 3.78)
            margin_mm = 40  # 2cm margins on each side
            page_width_mm = table_width_mm + margin_mm
            
            # Ensure reasonable minimum and maximum page sizes
            page_width_mm = max(page_width_mm, 420)  # At least A3 landscape width
            page_width_mm = min(page_width_mm, 2000)  # Increased max width for very wide tables
            
            page_width = f"{page_width_mm}mm"
            page_height = "420mm"  # Use A2 height for very wide tables
            page_size = f"{page_width} {page_height}"
            margin = "2cm 2cm"
            orientation = f"custom ({page_width_mm}mm wide)"
            
            logger.info(
                "Using custom page size %s for %d columns with total width %d px",
                page_size,
                len(dataframe.columns),
                estimated_table_width
            )
        
        logger.info(
            "Selected page size: %s (%s) for table width %d px",
            page_size,
            orientation,
            estimated_table_width
        )
    else:
        # Default A4 portrait for smaller tables
        page_size = "A4"
        page_width = "210mm"
        page_height = "297mm"
        margin = "2cm 1.5cm"
        orientation = "portrait"
    
    # CSS for proper PDF formatting with dynamic page sizing
    # Generate dynamic CSS based on table width
    if estimated_table_width > 1200:
        table_font_size = "7pt"
        cell_padding = "3px 6px"
    else:
        table_font_size = "8pt"
        cell_padding = "4px 8px"
    
    css_styles = f"""
    <style type="text/css">
        @page {{
            size: {page_size};
            margin: {margin};
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10pt;
                color: #666;
            }}
        }}
        
        body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.4;
            color: #333;
            margin: 0;
            padding: 0;
            width: 100%;
            overflow-x: auto;
        }}
        
        .header {{
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .title {{
            font-size: 18pt;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 8px;
        }}
        
        .description {{
            font-size: 11pt;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: {table_font_size};
            margin-top: 10px;
            table-layout: fixed;  /* Use fixed layout for better control */
            word-wrap: break-word;
        }}
        
        .data-table th {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: {cell_padding};
            text-align: left;
            font-weight: bold;
            color: #495057;
            page-break-inside: avoid;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            /* Remove max-width constraint to prevent column truncation */
        }}
        
        .data-table td {{
            border: 1px solid #dee2e6;
            padding: {cell_padding};
            text-align: left;
            page-break-inside: avoid;
            word-wrap: break-word;
            overflow: hidden;
            /* Remove max-width constraint to prevent column truncation */
        }}
        
        .data-table tbody tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        .data-table tbody tr:hover {{
            background-color: #e9ecef;
        }}
        
        /* Prevent table headers from breaking across pages */
        .data-table thead {{
            display: table-header-group;
        }}
        
        .data-table tbody {{
            display: table-row-group;
        }}
        
        /* Allow page breaks within table body */
        .data-table tbody tr {{
            page-break-inside: avoid;
            page-break-after: auto;
        }}
        
        /* Ensure table continues header on new pages */
        .data-table {{
            page-break-before: auto;
            page-break-after: auto;
            page-break-inside: auto;
        }}
        
        /* Specific styling for index column */
        .data-table th:first-child,
        .data-table td:first-child {{
            background-color: #e9ecef;
            font-weight: bold;
            text-align: center;
            width: 8%;  /* Use percentage instead of fixed width */
            min-width: 50px;
        }}
        
        /* Dynamic column width based on number of columns */
        .data-table th:not(:first-child),
        .data-table td:not(:first-child) {{
            width: {92 / len(dataframe.columns) if len(dataframe.columns) > 0 else 10}%;
            min-width: 80px;  /* Ensure minimum visibility */
        }}
        
        /* Ensure all columns are visible - no hiding */
        .data-table th,
        .data-table td {{
            display: table-cell !important;
            visibility: visible !important;
        }}
        
        /* For very wide tables, allow horizontal scrolling in print */
        @media print {{
            .data-table {{
                font-size: {table_font_size};
                width: 100%;
                table-layout: fixed;
            }}
            .data-table th,
            .data-table td {{
                padding: {cell_padding};
                word-wrap: break-word;
                overflow-wrap: break-word;
            }}
        }}
    </style>
    """
    
    # Complete HTML document
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        {css_styles}
    </head>
    <body>
        <div class="header">
            <div class="title">{title}</div>
            {f'<div class="description">{description}</div>' if description else ''}
        </div>
        {table_html}
    </body>
    </html>
    """
    
    return html_content


def build_pdf_from_html(html_content: str) -> bytes:
    """
    Generate PDF from HTML content using WeasyPrint.
    
    :param html_content: Complete HTML document string
    :return: PDF bytes
    :raises: ReportSchedulePdfFailedError if conversion fails
    """
    if weasyprint is None:
        raise ReportSchedulePdfFailedError(
            "WeasyPrint is not installed - cannot generate PDF from HTML"
        )
    
    try:
        logger.info("Converting HTML to PDF using WeasyPrint")
        # Generate PDF from HTML
        pdf_document = weasyprint.HTML(string=html_content)
        pdf_bytes = pdf_document.write_pdf()
        
        logger.info("Successfully generated PDF from HTML")
        return pdf_bytes
        
    except Exception as ex:
        raise ReportSchedulePdfFailedError(
            f"Failed converting HTML to PDF: {str(ex)}"
        ) from ex


def build_pdf_from_dataframe(
    dataframe, 
    title: str = "Report", 
    description: str = "",
    auto_resize_page: bool = True
) -> bytes:
    """
    Generate PDF from pandas DataFrame using HTML conversion.
    
    :param dataframe: The pandas DataFrame to convert
    :param title: The title for the report  
    :param description: Optional description text
    :param auto_resize_page: Whether to automatically resize page based on table width
    :return: PDF bytes
    :raises: ReportSchedulePdfFailedError if conversion fails
    """
    logger.info("Starting build_pdf_from_dataframe with auto_resize_page=%s", auto_resize_page)
    
    if pd is None:
        logger.error("pandas is None - pandas not available")
        raise ReportSchedulePdfFailedError("pandas is required for DataFrame to PDF conversion")
    
    if not WEASYPRINT_AVAILABLE or weasyprint is None:
        logger.error("WeasyPrint not available - cannot generate multi-page PDF with dynamic sizing")
        logger.error("This means the enhanced PDF generation will fail and fall back to basic A4 portrait PDF")
        logger.error("To fix this on Windows, install GTK libraries or use Windows Subsystem for Linux (WSL)")
        raise ReportSchedulePdfFailedError(
            "WeasyPrint is not available - GTK system libraries required on Windows. "
            "Enhanced PDF generation with dynamic page sizing is not available. "
            "The system will fall back to basic A4 portrait PDF generation."
        )
    
    logger.info("pandas and weasyprint are available, proceeding with PDF generation")
    
    try:
        html_content = generate_table_html(dataframe, title, description, auto_resize_page)
        logger.info("Generated HTML content, length: %d characters", len(html_content))
        
        pdf_bytes = build_pdf_from_html(html_content)
        logger.info("Successfully converted HTML to PDF, size: %d bytes", len(pdf_bytes))
        
        return pdf_bytes
    except Exception as ex:
        logger.error("Error in build_pdf_from_dataframe: %s", str(ex))
        raise ReportSchedulePdfFailedError(
            f"Failed generating PDF from DataFrame: {str(ex)}"
        ) from ex


def build_pdf_from_screenshots(snapshots: list[bytes]) -> bytes:
    if not snapshots:
        raise ReportSchedulePdfFailedError("No screenshots provided for PDF generation")
        
    try:
        from PIL import Image
    except ImportError as ex:
        raise ReportSchedulePdfFailedError(
            "PIL/Pillow is required for screenshot-based PDF generation"
        ) from ex
        
    images = []

    for snap in snapshots:
        img = Image.open(BytesIO(snap))
        if img.mode == "RGBA":
            img = img.convert("RGB")
        images.append(img)
    logger.info("building pdf")
    try:
        new_pdf = BytesIO()
        images[0].save(new_pdf, "PDF", save_all=True, append_images=images[1:])
        new_pdf.seek(0)
    except Exception as ex:
        raise ReportSchedulePdfFailedError(
            f"Failed converting screenshots to pdf {str(ex)}"
        ) from ex

    return new_pdf.read()
