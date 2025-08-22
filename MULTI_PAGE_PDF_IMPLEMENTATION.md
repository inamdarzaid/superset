# Multi-Page PDF Generation Implementation

## Overview

This implementation adds support for generating multi-page PDFs from table data in Superset reports, replacing screenshot-based PDFs with HTML-to-PDF conversion using WeasyPrint.

## Changes Made

### 1. Added WeasyPrint Dependency

**File**: `requirements/base.in`
- Added `weasyprint>=61.0` as a new dependency for HTML-to-PDF conversion

### 2. Enhanced PDF Utility Functions

**File**: `superset/utils/pdf.py`

Added new functions for HTML-to-PDF conversion:

- `generate_table_html()`: Converts pandas DataFrame to properly formatted HTML
  - Includes CSS for multi-page layout
  - Adds page headers, footers, and page numbering
  - Ensures table headers repeat on each page
  - Provides professional styling

- `build_pdf_from_html()`: Converts HTML to PDF using WeasyPrint
  - Handles WeasyPrint errors gracefully
  - Returns PDF as bytes

- `build_pdf_from_dataframe()`: Complete workflow for DataFrame to PDF
  - Combines HTML generation and PDF conversion
  - Accepts title and description parameters

### 3. Modified Report Execution Logic

**File**: `superset/commands/report/execute.py`

Enhanced the `_get_pdf()` method:
- **Smart Detection**: Checks if the chart is a table type (`table`, `pivot_table`, `pivot_table_v2`)
- **Full Data Access**: Uses `_get_embedded_data()` to get complete dataset (not just visible data)
- **Multi-page Support**: Generates PDF from full data using HTML conversion
- **Graceful Fallback**: Falls back to screenshot-based PDF if data-based generation fails

## Key Features

### 1. Complete Data Export
- Uses `embedded_data` which contains the full dataset from `ChartDataResultFormat.JSON`
- Not limited to currently visible/paginated data in the UI
- Includes all rows regardless of frontend pagination

### 2. Professional Multi-Page Layout
- **Page Headers**: Repeat table headers on every page
- **Page Breaks**: Intelligent page breaking to avoid splitting rows
- **Page Numbers**: Automatic page numbering in footer
- **Styling**: Professional table formatting with alternating row colors

### 3. CSS Features for PDF
```css
@page {
    size: A4;
    margin: 2cm 1.5cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
    }
}

/* Table headers repeat on each page */
.data-table thead {
    display: table-header-group;
}

/* Prevent row breaks across pages */
.data-table tbody tr {
    page-break-inside: avoid;
}
```

### 4. Error Handling
- Gracefully handles missing WeasyPrint installation
- Falls back to screenshot-based PDF generation on errors
- Provides detailed error logging

## Usage Flow

1. **Report Generation Request**: User requests PDF report for a table chart
2. **Chart Type Detection**: System checks if chart is table-based
3. **Data Retrieval**: `_get_embedded_data()` fetches complete dataset as DataFrame
4. **HTML Generation**: DataFrame converted to HTML with multi-page CSS
5. **PDF Conversion**: WeasyPrint converts HTML to multi-page PDF
6. **Fallback**: If any step fails, falls back to screenshot-based PDF

## Benefits

### Before (Screenshot-based)
- ❌ Limited to visible data only
- ❌ Single page screenshots stitched together
- ❌ Poor text quality (image-based)
- ❌ Large file sizes
- ❌ No searchable text

### After (HTML-to-PDF)
- ✅ Complete dataset included
- ✅ True multi-page layout
- ✅ High-quality text rendering
- ✅ Smaller file sizes
- ✅ Searchable PDF content
- ✅ Professional page headers/footers
- ✅ Proper page breaking

## Installation Requirements

After these changes, you'll need to:

1. **Install WeasyPrint**: Run `pip install weasyprint>=61.0` or use the updated requirements
2. **System Dependencies**: WeasyPrint may require system-level dependencies (varies by OS)

## Compatibility

- **Backward Compatible**: Existing screenshot-based PDF generation remains as fallback
- **Chart Types**: Currently enabled for `table`, `pivot_table`, and `pivot_table_v2` charts
- **Other Charts**: Non-table charts continue using screenshot-based PDF generation

## Future Enhancements

Potential improvements:
- Extend to other chart types with tabular data
- Add configuration options for PDF styling
- Support for custom page layouts
- Chart embedding alongside table data