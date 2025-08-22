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


def generate_table_html(
    dataframe: pd.DataFrame, 
    title: str = "Report", 
    description: str = ""
) -> str:
    """
    Generate HTML content for a pandas DataFrame with proper CSS for PDF generation.
    
    :param dataframe: The pandas DataFrame to convert to HTML
    :param title: The title for the report
    :param description: Optional description text
    :return: Complete HTML document string
    """
    # Convert DataFrame to HTML table
    table_html = dataframe.to_html(
        na_rep="", 
        index=True, 
        escape=False,
        classes="data-table",
        table_id="report-table"
    )
    
    # CSS for proper PDF formatting with multi-page support
    css_styles = """
    <style type="text/css">
        @page {
            size: A4;
            margin: 2cm 1.5cm;
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10pt;
                color: #666;
            }
        }
        
        body {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.4;
            color: #333;
            margin: 0;
            padding: 0;
        }
        
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
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 8pt;
            margin-top: 10px;
        }
        
        .data-table th {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 6px 8px;
            text-align: left;
            font-weight: bold;
            color: #495057;
            page-break-inside: avoid;
        }
        
        .data-table td {
            border: 1px solid #dee2e6;
            padding: 4px 8px;
            text-align: left;
            page-break-inside: avoid;
        }
        
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
        .data-table td:first-child {
            background-color: #e9ecef;
            font-weight: bold;
            text-align: center;
            width: 60px;
        }
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
    description: str = ""
) -> bytes:
    """
    Generate PDF from pandas DataFrame using HTML conversion.
    
    :param dataframe: The pandas DataFrame to convert
    :param title: The title for the report  
    :param description: Optional description text
    :return: PDF bytes
    :raises: ReportSchedulePdfFailedError if conversion fails
    """
    try:
        html_content = generate_table_html(dataframe, title, description)
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
