import requests
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, Any, Optional
import argparse
import json


class CloudabilityReporter:
    """
    A class to handle fetching, processing, and exporting Cloudability cost reports.

    Attributes:
        api_key (str): Cloudability API authentication key
        base_url (str): Base URL for Cloudability API
        headers (dict): HTTP headers for API requests
        views_config (dict): Configuration for different cloud provider views
        logger (Logger): Logger instance for the class
    """

    def __init__(self, api_key: str, views_file: str):
        """
        Initialize the CloudabilityReporter with API key and views configuration.

        Args:
            api_key (str): Cloudability API authentication key
            views_file (str): Path to JSON file containing view configurations

        Raises:
            FileNotFoundError: If views_file doesn't exist
            json.JSONDecodeError: If views_file is not valid JSON
        """
        self.api_key = api_key
        self.base_url = 'https://api.cloudability.com/v3'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # Load views configuration
        with open(views_file, 'r') as f:
            self.views_config = json.load(f)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def get_report(
        self,
        cloud_provider: str,
        view_name: str,
        start_date: str,
        end_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch cost report data from Cloudability API for specified provider and view.

        Args:
            cloud_provider (str): Cloud provider name ('AWS', 'Azure')
            view_name (str): Name of the view configuration to use
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format

        Returns:
            Optional[Dict[str, Any]]: JSON response from API containing report data
                                    None if request fails or config is invalid

        Raises:
            requests.exceptions.RequestException: If API request fails
        """
        try:
            if cloud_provider not in self.views_config:
                self.logger.error(f'Invalid cloud provider: {cloud_provider}')
                return None

            if view_name not in self.views_config[cloud_provider]:
                self.logger.error(
                    f'Invalid view name for {cloud_provider}: {view_name}'
                )
                return None

            view_config = self.views_config[cloud_provider][view_name]
            endpoint = f'{self.base_url}/reports/cost'

            params = {
                'start_date': start_date,
                'end_date': end_date,
                'dimensions': view_config['dimensions'],
                'metrics': view_config['metrics']
            }

            self.logger.info(f'Fetching {cloud_provider} report with view {view_name}')
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f'Error fetching report: {str(e)}')
            return None

    def process_data(self, data: Dict[str, Any], view_name: str) -> Optional[pd.DataFrame]:
        """
        Process raw API response data into a pandas DataFrame.
        Optimized for large datasets (millions of rows).

        Args:
            data (Dict[str, Any]): Raw JSON response from Cloudability API
            view_name (str): Name of the view configuration used

        Returns:
            Optional[pd.DataFrame]: Processed DataFrame with cost data
                                  None if processing fails
        """
        try:
            self.logger.info(f'Processing data for view {view_name}')

            # Create DataFrame with optimized data types
            df = pd.DataFrame(data['data'])

            if not df.empty:
                # Optimize numeric columns
                for col in df.select_dtypes(include=['float64']).columns:
                    df[col] = pd.to_numeric(df[col], downcast='float')
                for col in df.select_dtypes(include=['int64']).columns:
                    df[col] = pd.to_numeric(df[col], downcast='integer')

                # Clean up column names
                df.columns = df.columns.str.lower().str.replace(' ', '_')

            return df

        except Exception as e:
            self.logger.error(f'Error processing data: {str(e)}')
            return None

    def export_to_excel(
        self,
        cloud_data: Dict[str, pd.DataFrame],
        filename: str
    ) -> bool:
        """
        Export processed data to Excel file with separate worksheets for each provider.
        Optimized for large datasets using chunked writing.

        Args:
            cloud_data (Dict[str, pd.DataFrame]): Dict mapping providers to DataFrames
            filename (str): Name of the output Excel file

        Returns:
            bool: True if export successful, False otherwise
        """
        try:
            self.logger.info(f'Exporting data to {filename}')
            CHUNK_SIZE = 100000  # Process 100k rows at a time

            writer_options = {'options': {'constant_memory': True}}
            with pd.ExcelWriter(
                filename,
                engine='xlsxwriter',
                engine_kwargs=writer_options
            ) as writer:
                workbook = writer.book
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#D3D3D3',
                    'border': 1
                })

                for provider, df in cloud_data.items():
                    sheet_name = f'{provider.lower()}_data'
                    total_rows = len(df)

                    # Write data in chunks
                    for start_idx in range(0, total_rows, CHUNK_SIZE):
                        end_idx = min(start_idx + CHUNK_SIZE, total_rows)
                        chunk = df.iloc[start_idx:end_idx]

                        if start_idx == 0:
                            # First chunk: write with header
                            chunk.to_excel(
                                writer,
                                sheet_name=sheet_name,
                                index=False,
                                startrow=0
                            )

                            # Format header
                            worksheet = writer.sheets[sheet_name]
                            for col_num, value in enumerate(df.columns.values):
                                worksheet.write(0, col_num, value, header_format)
                        else:
                            # Subsequent chunks: append without header
                            chunk.to_excel(
                                writer,
                                sheet_name=sheet_name,
                                index=False,
                                startrow=start_idx+1,
                                header=False
                            )

                    # Auto-adjust column widths (sample first 1000 rows)
                    worksheet = writer.sheets[sheet_name]
                    sample_data = df.head(1000)
                    for i, col in enumerate(df.columns):
                        max_length = max(
                            sample_data[col].astype(str).apply(len).max(),
                            len(str(col))
                        )
                        worksheet.set_column(i, i, max_length + 2)

                    self.logger.info(f'Exported {total_rows} rows for {provider}')

            self.logger.info('Export completed successfully')
            return True

        except Exception as e:
            self.logger.error(f'Error exporting to Excel: {str(e)}')
            return False


def main():
    API_KEY = 'your_api_key_here'
    VIEWS_FILE = 'views_config.json'

    parser = argparse.ArgumentParser(description='Export Cloudability reports to Excel')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    reporter = CloudabilityReporter(API_KEY, VIEWS_FILE)
    cloud_data = {}

    # Process each cloud provider and its views
    for provider in ['AWS', 'Azure']:
        dfs = []
        for view_name in reporter.views_config[provider].keys():
            data = reporter.get_report(
                provider,
                view_name,
                args.start_date,
                args.end_date
            )
            if data:
                df = reporter.process_data(data, view_name)
                if df is not None:
                    dfs.append(df)

        if dfs:
            cloud_data[provider] = pd.concat(dfs, ignore_index=True)

    if cloud_data:
        filename = f'cloudability_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
        reporter.export_to_excel(cloud_data, filename)


if __name__ == '__main__':
    main() 