# Cloudability Cost Report Exporter

A Python tool for exporting Cloudability cost reports for AWS and Azure cloud services to Excel format. This tool supports multiple view configurations and handles large datasets efficiently.

## Features

- Multi-cloud support (AWS and Azure)
- Configurable views via JSON configuration
- Category-based cost classification
- Chunked data processing for large datasets
- Excel export with formatted worksheets
- Comprehensive error handling and logging
- Memory-optimized for large datasets

## Prerequisites

- Python 3.9+
- Cloudability API access
- Required Python packages:
  - pandas
  - requests
  - xlsxwriter
  - openpyxl

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd cloudability-exporter
```

2. Install required packages:
```bash
pip install pandas requests xlsxwriter openpyxl
```

3. Configure your views in `views_config.json`:
```json
{
    "AWS": {
        "aws_view1": {
            "dimensions": ["service", "resource", "tags"],
            "metrics": ["cost"],
            "category": "core"
        },
        "aws_view2": {
            "dimensions": ["service", "resource", "tags", "account", "region"],
            "metrics": ["cost"],
            "category": "product1"
        }
    },
    "Azure": {
        "azure_view1": {
            "dimensions": ["service", "resource"],
            "metrics": ["cost"],
            "category": "product2"
        },
        "azure_view2": {
            "dimensions": ["service", "resource", "account", "region"],
            "metrics": ["cost"],
            "category": "product3"
        }
    }
}
```

## Usage

1. Set your Cloudability API key as an environment variable:
```bash
export CLOUDABILITY_API_KEY='your_cloudability_api_key'
```

2. Run the script:
```bash
python cloudability_reports.py --start-date 2024-01-01 --end-date 2024-01-31
```

### Command Line Arguments

- `--start-date`: Start date for the report (YYYY-MM-DD)
- `--end-date`: End date for the report (YYYY-MM-DD)

## Output

The script generates an Excel file with:
- Separate worksheets for AWS and Azure data
- Category as the first column for cost classification
- Formatted headers and columns
- Auto-adjusted column widths
- Filename format: `cloudability_report_YYYYMMDD.xlsx`

## Development

### Running Tests

Run the unit test suite:
```bash
python -m unittest test_cloudability_reports.py -v
```

### Test Coverage

The test suite covers:
- API interactions
- Data processing
- Excel export
- Error handling
- Multiple view configurations
- Both AWS and Azure providers
- Category field handling
- Environment variable configuration

## Memory Optimization

The tool is optimized for large datasets:
- Chunked data processing
- Memory-efficient Excel writing
- Data type optimization
- Configurable chunk sizes

## Error Handling

- Comprehensive logging
- Graceful error handling for:
  - API failures
  - Invalid configurations
  - Missing API key
  - Data processing errors
  - Excel export issues

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 