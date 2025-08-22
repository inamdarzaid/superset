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

import pandas as pd

from superset.commands.report.exceptions import ReportSchedulePdfFailedError

logger = logging.getLogger(__name__)
try:
    from PIL import Image
except ModuleNotFoundError:
    logger.info("No PIL installation found")
    
try:
    import weasyprint
except ModuleNotFoundError:
    logger.info("No WeasyPrint installation found - HTML to PDF conversion not available")
    weasyprint = None


def estimate_table_width(dataframe: pd.DataFrame) -> int:
    """
    Estimate the width required for a table based on its content.
    
    :param dataframe: The pandas DataFrame to analyze
    :return: Estimated width in pixels
    """
    if dataframe.empty:
        return 300  # Minimum width for empty tables
    
    total_width = 80  # Base width for index column
    
    for column in dataframe.columns:
        # Column header width
        header_width = len(str(column)) * 8 + 20  # ~8px per character + padding
        
        # Sample content width (check first few rows for performance)
        sample_size = min(10, len(dataframe))
        content_widths = []
        
        for value in dataframe[column].head(sample_size):
            if pd.isna(value):
                content_widths.append(30)  # Width for empty/NA values
            else:
                # Estimate based on string length
                str_value = str(value)
                if len(str_value) > 50:  # Very long content
                    content_widths.append(400)  # Cap at reasonable width
                else:
                    content_widths.append(len(str_value) * 8 + 16)
        
        # Use the maximum of header width and average content width
        avg_content_width = sum(content_widths) / len(content_widths) if content_widths else 50
        column_width = max(header_width, avg_content_width, 80)  # Minimum 80px per column
        column_width = min(column_width, 250)  # Maximum 250px per column to prevent excessive width
        
        total_width += column_width
    
    return int(total_width)


def generate_table_html(
    dataframe: pd.DataFrame, 
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
    # Calculate estimated table width for dynamic page sizing
    estimated_table_width = estimate_table_width(dataframe)
    
    logger.info(
        "Generating PDF for table with %d columns, %d rows, estimated width: %d px",
        len(dataframe.columns),
        len(dataframe),
        estimated_table_width
    )
    
    # Convert DataFrame to HTML table
    table_html = dataframe.to_html(
        na_rep="", 
        index=True, 
        escape=False,
        classes="data-table",
        table_id="report-table"
    )
    
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
            # Convert pixels to mm (roughly 3.78 pixels per mm)
            table_width_mm = int(estimated_table_width / 3.78)
            margin_mm = 40  # 2cm margins on each side
            page_width_mm = table_width_mm + margin_mm
            
            # Ensure reasonable minimum and maximum page sizes
            page_width_mm = max(page_width_mm, 420)  # At least A3 landscape width
            page_width_mm = min(page_width_mm, 1682)  # Max A0 width
            
            page_width = f"{page_width_mm}mm"
            page_height = "420mm"  # Use A2 height for very wide tables
            page_size = f"{page_width} {page_height}"
            margin = "2cm 2cm"
            orientation = "custom"
        
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
        
        .header {
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .title {
            font-size: 18pt;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        
        .description {
            font-size: 11pt;
            color: #666;
            margin-bottom: 10px;
        }
        
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8pt;
            margin-top: 10px;
            table-layout: auto;
            word-wrap: break-word;
        }}
        
        .data-table th {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 6px 8px;
            text-align: left;
            font-weight: bold;
            color: #495057;
            page-break-inside: avoid;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 150px;
        }}
        
        .data-table td {{
            border: 1px solid #dee2e6;
            padding: 4px 8px;
            text-align: left;
            page-break-inside: avoid;
            word-wrap: break-word;
            max-width: 150px;
            overflow: hidden;
        }}
        
        .data-table tbody tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .data-table tbody tr:hover {
            background-color: #e9ecef;
        }
        
        /* Prevent table headers from breaking across pages */
        .data-table thead {
            display: table-header-group;
        }
        
        .data-table tbody {
            display: table-row-group;
        }
        
        /* Allow page breaks within table body */
        .data-table tbody tr {
            page-break-inside: avoid;
            page-break-after: auto;
        }
        
        /* Ensure table continues header on new pages */
        .data-table {
            page-break-before: auto;
            page-break-after: auto;
            page-break-inside: auto;
        }
        
        /* Specific styling for index column */
        .data-table th:first-child,
        .data-table td:first-child {{
            background-color: #e9ecef;
            font-weight: bold;
            text-align: center;
            width: 60px;
            min-width: 60px;
            max-width: 80px;
        }}
        
        /* Responsive adjustments for very wide tables */
        @media print {{
            .data-table {{
                font-size: {"7pt" if estimated_table_width > 1200 else "8pt"};
            }}
            .data-table th,
            .data-table td {{
                padding: {"3px 6px" if estimated_table_width > 1200 else "4px 8px"};
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
    dataframe: pd.DataFrame, 
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
    try:
        html_content = generate_table_html(dataframe, title, description, auto_resize_page)
        return build_pdf_from_html(html_content)
    except Exception as ex:
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
