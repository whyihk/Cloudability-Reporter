import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import pandas as pd
import requests
from cloudability_reports import CloudabilityReporter


class TestCloudabilityReporter(unittest.TestCase):
    """
    Test suite for CloudabilityReporter class.
    Tests the functionality of fetching, processing, and exporting cloud cost reports.
    """

    def setUp(self):
        """
        Set up test fixtures before each test method.
        Creates a mock configuration that mimics the structure of views_config.json:
        - AWS views with different dimensions and metrics
        - Azure views with different dimensions and metrics
        Initializes a CloudabilityReporter instance with test API key
        """
        self.mock_views_config = {
            "AWS": {
                "aws_view1": {
                    "dimensions": ["service", "resource", "tags"],
                    "metrics": ["cost"]
                },
                "aws_view2": {
                    "dimensions": [
                        "service",
                        "resource",
                        "tags",
                        "account",
                        "region"
                    ],
                    "metrics": ["cost"]
                }
            },
            "Azure": {
                "azure_view1": {
                    "dimensions": ["service", "resource"],
                    "metrics": ["cost"]
                },
                "azure_view2": {
                    "dimensions": ["service", "resource", "account", "region"],
                    "metrics": ["cost"]
                }
            }
        }

        # Mock the file reading operation to avoid actual file system access
        with patch(
            'builtins.open',
            mock_open(read_data=json.dumps(self.mock_views_config))
        ):
            self.reporter = CloudabilityReporter('test_api_key', 'mock_views.json')

    def test_init(self):
        """
        Test the initialization of CloudabilityReporter.

        Verifies:
        1. API key is correctly stored
        2. Base URL is set to the correct endpoint
        3. Views configuration is properly loaded from file
        4. HTTP headers are correctly formatted with Bearer token
        """
        self.assertEqual(self.reporter.api_key, 'test_api_key')
        self.assertEqual(self.reporter.base_url, 'https://api.cloudability.com/v3')
        self.assertEqual(self.reporter.views_config, self.mock_views_config)
        self.assertEqual(
            self.reporter.headers,
            {
                'Authorization': 'Bearer test_api_key',
                'Content-Type': 'application/json'
            }
        )

    @patch('requests.get')
    def test_get_report_success(self, mock_get):
        """
        Test successful AWS report retrieval with aws_view1 configuration.

        Test Data:
        - Uses aws_view1 dimensions: service, resource, tags
        - Uses aws_view1 metrics: cost

        Mocks:
        - HTTP GET request to Cloudability API
        - Response with AWS EC2 instance data

        Verifies:
        1. API returns data matching aws_view1 structure
        2. All required dimensions are present
        3. Cost metric is included
        4. API is called exactly once
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [{
                'service': 'EC2',
                'resource': 'i-1234567890',
                'tags': {'Environment': 'Production'},
                'cost': 100
            }]
        }
        mock_get.return_value = mock_response

        result = self.reporter.get_report(
            'AWS',
            'aws_view1',
            '2024-01-01',
            '2024-01-31'
        )

        self.assertEqual(result, mock_response.json())
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_get_report_invalid_provider(self, mock_get):
        """
        Test error handling when an invalid cloud provider is specified.

        Scenario:
        - Attempts to fetch report for non-existent provider 'GCP'

        Verifies:
        1. Returns None for invalid provider
        2. No API call is made
        3. Error is properly logged
        """
        result = self.reporter.get_report(
            'GCP',  # Invalid provider
            'aws_view1',
            '2024-01-01',
            '2024-01-31'
        )

        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch('requests.get')
    def test_get_report_invalid_view(self, mock_get):
        """
        Test get_report with invalid view name.

        Verifies:
        1. Returns None for invalid view
        2. No API call is made
        3. Error is properly logged
        """
        result = self.reporter.get_report(
            'AWS',
            'invalid_view',  # Invalid view
            '2024-01-01',
            '2024-01-31'
        )

        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch('requests.get')
    def test_get_report_api_error(self, mock_get):
        """
        Test get_report handling of API errors.

        Verifies:
        1. Returns None when API request fails
        2. Error is properly logged
        """
        mock_get.side_effect = requests.exceptions.RequestException('API Error')

        result = self.reporter.get_report(
            'AWS',
            'aws_view1',
            '2024-01-01',
            '2024-01-31'
        )

        self.assertIsNone(result)

    def test_process_data_success(self):
        """
        Test successful data processing.

        Verifies:
        1. Returns a valid DataFrame
        2. DataFrame has correct number of rows
        3. Column names are properly formatted
        4. Category is the first column
        """
        mock_data = {
            'data': [
                {'service': 'EC2', 'cost': 100},
                {'service': 'S3', 'cost': 200}
            ]
        }

        result = self.reporter.process_data(mock_data, 'aws_view1')

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        expected_columns = {'category', 'service', 'cost'}
        self.assertEqual(set(result.columns), expected_columns)
        self.assertEqual(result.columns[0], 'category')
        self.assertEqual(result['category'].iloc[0], 'core')  # Check category value

    def test_process_data_empty(self):
        """
        Test processing empty data.

        Verifies:
        1. Returns an empty DataFrame
        2. DataFrame has correct structure
        """
        mock_data = {'data': []}

        result = self.reporter.process_data(mock_data, 'aws_view1')

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 0)

    def test_process_data_invalid(self):
        """
        Test processing invalid data.

        Verifies:
        1. Returns None for invalid data structure
        2. Error is properly logged
        """
        mock_data = {'invalid_key': []}

        result = self.reporter.process_data(mock_data, 'aws_view1')

        self.assertIsNone(result)

    @patch('pandas.ExcelWriter')
    def test_export_to_excel_success(self, mock_writer):
        """
        Test successful export of data to Excel file.

        Mocks:
        - Excel writer and workbook objects
        - DataFrame export operations

        Verifies:
        1. Excel file is created with correct formatting
        2. Data is written to appropriate sheets
        3. Export operation completes successfully
        4. Proper worksheet formatting is applied
        """
        mock_data = {
            'AWS': pd.DataFrame({
                'service': ['EC2', 'S3'],
                'cost': [100, 200]
            })
        }

        # Create comprehensive mocks for Excel writing
        mock_workbook = MagicMock()
        mock_worksheet = MagicMock()
        mock_format = MagicMock()

        writer_instance = MagicMock()
        writer_instance.book = mock_workbook
        writer_instance.sheets = {'aws_data': mock_worksheet}

        mock_writer.return_value.__enter__.return_value = writer_instance
        mock_writer.return_value.__exit__.return_value = None
        mock_workbook.add_format.return_value = mock_format

        # Mock DataFrame export
        mock_data['AWS'].to_excel = MagicMock()

        with patch('pandas.DataFrame.to_excel'):
            result = self.reporter.export_to_excel(mock_data, 'test.xlsx')
            self.assertTrue(result)

    @patch('pandas.ExcelWriter')
    def test_export_to_excel_error(self, mock_writer):
        """
        Test error handling during Excel export operation.

        Scenario:
        - Simulates failure during Excel file creation

        Verifies:
        1. Error is caught and handled gracefully
        2. Method returns False on failure
        3. Error is properly logged
        4. No partial file is created
        """
        mock_data = {
            'AWS': pd.DataFrame({
                'service': ['EC2', 'S3'],
                'cost': [100, 200]
            })
        }

        # Simulate Excel writing error
        mock_writer.side_effect = Exception('Excel Error')

        result = self.reporter.export_to_excel(mock_data, 'test.xlsx')

        self.assertFalse(result)

    @patch('requests.get')
    def test_get_report_success_azure(self, mock_get):
        """
        Test successful Azure report retrieval with azure_view1 configuration.

        Test Data:
        - Uses azure_view1 dimensions: service, resource
        - Uses azure_view1 metrics: cost

        Mocks:
        - HTTP GET request to Cloudability API
        - Response with Azure VM data

        Verifies:
        1. API returns data matching azure_view1 structure
        2. All required dimensions are present
        3. Cost metric is included
        4. API is called exactly once
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [{
                'service': 'VirtualMachines',
                'resource': 'vm-prod-01',
                'cost': 150
            }]
        }
        mock_get.return_value = mock_response

        result = self.reporter.get_report(
            'Azure',
            'azure_view1',
            '2024-01-01',
            '2024-01-31'
        )

        self.assertEqual(result, mock_response.json())
        mock_get.assert_called_once()

    def test_process_data_success_both_providers(self):
        """
        Test data processing for both AWS and Azure with their most detailed views.

        Test Data:
        AWS (aws_view2):
        - Dimensions: service, resource, tags, account, region
        - Sample data: EC2 and S3 services with full dimension set

        Azure (azure_view2):
        - Dimensions: service, resource, account, region
        - Sample data: VM and Storage services with full dimension set

        Verifies:
        1. Both providers' data is processed correctly
        2. All dimensions from views_config.json are present
        3. DataFrames maintain correct structure
        4. Column names match configuration
        5. Data types are preserved
        6. Category is the first column with correct value
        """
        mock_aws_data = {
            'data': [
                {
                    'service': 'EC2',
                    'resource': 'i-1234567890',
                    'tags': {'Environment': 'Production'},
                    'account': '123456789012',
                    'region': 'us-west-2',
                    'cost': 100
                },
                {
                    'service': 'S3',
                    'resource': 'my-bucket',
                    'tags': {'Project': 'Data'},
                    'account': '123456789012',
                    'region': 'us-east-1',
                    'cost': 200
                }
            ]
        }

        mock_azure_data = {
            'data': [
                {
                    'service': 'VirtualMachines',
                    'resource': 'vm-prod-01',
                    'account': 'subscription-1',
                    'region': 'eastus',
                    'cost': 150
                },
                {
                    'service': 'Storage',
                    'resource': 'storage-prod',
                    'account': 'subscription-1',
                    'region': 'westus',
                    'cost': 250
                }
            ]
        }

        aws_result = self.reporter.process_data(mock_aws_data, 'aws_view2')
        self.assertIsInstance(aws_result, pd.DataFrame)
        self.assertEqual(len(aws_result), 2)
        expected_aws_columns = {
            'category', 'service', 'resource', 'tags', 'account', 'region', 'cost'
        }
        self.assertEqual(set(aws_result.columns), expected_aws_columns)
        self.assertEqual(aws_result.columns[0], 'category')
        self.assertEqual(aws_result['category'].iloc[0], 'product1')

        azure_result = self.reporter.process_data(mock_azure_data, 'azure_view2')
        self.assertIsInstance(azure_result, pd.DataFrame)
        self.assertEqual(len(azure_result), 2)
        expected_azure_columns = {
            'category', 'service', 'resource', 'account', 'region', 'cost'
        }
        self.assertEqual(set(azure_result.columns), expected_azure_columns)
        self.assertEqual(azure_result.columns[0], 'category')
        self.assertEqual(azure_result['category'].iloc[0], 'product3')

    @patch('pandas.ExcelWriter')
    def test_export_to_excel_both_providers(self, mock_writer):
        """
        Test Excel export with both AWS and Azure data using their full dimension sets.

        Test Data:
        AWS Sheet:
        - Full aws_view2 dimension set
        - Multiple services (EC2, S3)
        - Complete metadata (tags, account, region)

        Azure Sheet:
        - Full azure_view2 dimension set
        - Multiple services (VM, Storage)
        - Complete metadata (account, region)

        Mocks:
        - Excel writer and workbook objects
        - Separate worksheets for AWS and Azure
        - Header formatting

        Verifies:
        1. Separate sheets created for each provider
        2. All dimensions included in export
        3. Proper formatting applied
        4. Export completes successfully
        5. Data integrity maintained
        """
        mock_data = {
            'AWS': pd.DataFrame({
                'service': ['EC2', 'S3'],
                'resource': ['i-1234567890', 'my-bucket'],
                'tags': [{'Environment': 'Production'}, {'Project': 'Data'}],
                'account': ['123456789012', '123456789012'],
                'region': ['us-west-2', 'us-east-1'],
                'cost': [100, 200]
            }),
            'Azure': pd.DataFrame({
                'service': ['VirtualMachines', 'Storage'],
                'resource': ['vm-prod-01', 'storage-prod'],
                'account': ['subscription-1', 'subscription-1'],
                'region': ['eastus', 'westus'],
                'cost': [150, 250]
            })
        }

        # Create mocks for Excel writing
        mock_workbook = MagicMock()
        mock_worksheet_aws = MagicMock()
        mock_worksheet_azure = MagicMock()
        mock_format = MagicMock()

        writer_instance = MagicMock()
        writer_instance.book = mock_workbook
        writer_instance.sheets = {
            'aws_data': mock_worksheet_aws,
            'azure_data': mock_worksheet_azure
        }

        mock_writer.return_value.__enter__.return_value = writer_instance
        mock_writer.return_value.__exit__.return_value = None
        mock_workbook.add_format.return_value = mock_format

        with patch('pandas.DataFrame.to_excel'):
            result = self.reporter.export_to_excel(mock_data, 'test.xlsx')

        self.assertTrue(result)

    @patch('requests.get')
    def test_get_report_aws_all_views(self, mock_get):
        """
        Test AWS report retrieval for all configured views (aws_view1 and aws_view2).

        Test Data:
        aws_view1:
        - Dimensions: service, resource, tags
        - Metrics: cost

        aws_view2:
        - Dimensions: service, resource, tags, account, region
        - Metrics: cost

        Verifies:
        1. Each view returns correct dimension set
        2. API is called correctly for each view
        3. Data structure matches view configuration
        4. All required fields are present
        """
        # Mock response for aws_view1
        mock_response_view1 = MagicMock()
        mock_response_view1.json.return_value = {
            'data': [{
                'service': 'EC2',
                'resource': 'i-1234567890',
                'tags': {'Environment': 'Production'},
                'cost': 100
            }]
        }

        # Mock response for aws_view2
        mock_response_view2 = MagicMock()
        mock_response_view2.json.return_value = {
            'data': [{
                'service': 'EC2',
                'resource': 'i-1234567890',
                'tags': {'Environment': 'Production'},
                'account': '123456789012',
                'region': 'us-west-2',
                'cost': 100
            }]
        }

        # Test aws_view1
        mock_get.return_value = mock_response_view1
        result_view1 = self.reporter.get_report(
            'AWS',
            'aws_view1',
            '2024-01-01',
            '2024-01-31'
        )
        self.assertEqual(result_view1, mock_response_view1.json())

        # Test aws_view2
        mock_get.return_value = mock_response_view2
        result_view2 = self.reporter.get_report(
            'AWS',
            'aws_view2',
            '2024-01-01',
            '2024-01-31'
        )
        self.assertEqual(result_view2, mock_response_view2.json())

    @patch('requests.get')
    def test_get_report_azure_all_views(self, mock_get):
        """
        Test Azure report retrieval for all configured views (azure_view1 and azure_view2).

        Test Data:
        azure_view1:
        - Dimensions: service, resource
        - Metrics: cost

        azure_view2:
        - Dimensions: service, resource, account, region
        - Metrics: cost

        Verifies:
        1. Each view returns correct dimension set
        2. API is called correctly for each view
        3. Data structure matches view configuration
        4. All required fields are present
        """
        # Mock response for azure_view1
        mock_response_view1 = MagicMock()
        mock_response_view1.json.return_value = {
            'data': [{
                'service': 'VirtualMachines',
                'resource': 'vm-prod-01',
                'cost': 150
            }]
        }

        # Mock response for azure_view2
        mock_response_view2 = MagicMock()
        mock_response_view2.json.return_value = {
            'data': [{
                'service': 'VirtualMachines',
                'resource': 'vm-prod-01',
                'account': 'subscription-1',
                'region': 'eastus',
                'cost': 150
            }]
        }

        # Test azure_view1
        mock_get.return_value = mock_response_view1
        result_view1 = self.reporter.get_report(
            'Azure',
            'azure_view1',
            '2024-01-01',
            '2024-01-31'
        )
        self.assertEqual(result_view1, mock_response_view1.json())

        # Test azure_view2
        mock_get.return_value = mock_response_view2
        result_view2 = self.reporter.get_report(
            'Azure',
            'azure_view2',
            '2024-01-01',
            '2024-01-31'
        )
        self.assertEqual(result_view2, mock_response_view2.json())

    def test_process_data_all_views(self):
        """
        Test data processing for all views of both AWS and Azure.

        Test Data:
        AWS:
        - aws_view1: service, resource, tags (category: core)
        - aws_view2: service, resource, tags, account, region (category: product1)

        Azure:
        - azure_view1: service, resource (category: product2)
        - azure_view2: service, resource, account, region (category: product3)

        Verifies:
        1. Each view's data is processed correctly
        2. All dimensions from each view are present
        3. DataFrames maintain correct structure per view
        4. Column names match view configurations
        5. Data types are preserved
        6. Category is the first column with correct value for each view
        """
        # AWS View 1 data
        aws_view1_data = {
            'data': [{
                'service': 'EC2',
                'resource': 'i-1234567890',
                'tags': {'Environment': 'Production'},
                'cost': 100
            }]
        }

        # AWS View 2 data
        aws_view2_data = {
            'data': [{
                'service': 'EC2',
                'resource': 'i-1234567890',
                'tags': {'Environment': 'Production'},
                'account': '123456789012',
                'region': 'us-west-2',
                'cost': 100
            }]
        }

        # Azure View 1 data
        azure_view1_data = {
            'data': [{
                'service': 'VirtualMachines',
                'resource': 'vm-prod-01',
                'cost': 150
            }]
        }

        # Azure View 2 data
        azure_view2_data = {
            'data': [{
                'service': 'VirtualMachines',
                'resource': 'vm-prod-01',
                'account': 'subscription-1',
                'region': 'eastus',
                'cost': 150
            }]
        }

        # Test AWS View 1
        aws_v1_result = self.reporter.process_data(aws_view1_data, 'aws_view1')
        self.assertIsInstance(aws_v1_result, pd.DataFrame)
        self.assertEqual(
            set(aws_v1_result.columns),
            {'category', 'service', 'resource', 'tags', 'cost'}
        )
        self.assertEqual(aws_v1_result.columns[0], 'category')
        self.assertEqual(aws_v1_result['category'].iloc[0], 'core')

        # Test AWS View 2
        aws_v2_result = self.reporter.process_data(aws_view2_data, 'aws_view2')
        self.assertIsInstance(aws_v2_result, pd.DataFrame)
        self.assertEqual(
            set(aws_v2_result.columns),
            {'category', 'service', 'resource', 'tags', 'account', 'region', 'cost'}
        )
        self.assertEqual(aws_v2_result.columns[0], 'category')
        self.assertEqual(aws_v2_result['category'].iloc[0], 'product1')

        # Test Azure View 1
        azure_v1_result = self.reporter.process_data(azure_view1_data, 'azure_view1')
        self.assertIsInstance(azure_v1_result, pd.DataFrame)
        self.assertEqual(
            set(azure_v1_result.columns),
            {'category', 'service', 'resource', 'cost'}
        )
        self.assertEqual(azure_v1_result.columns[0], 'category')
        self.assertEqual(azure_v1_result['category'].iloc[0], 'product2')

        # Test Azure View 2
        azure_v2_result = self.reporter.process_data(azure_view2_data, 'azure_view2')
        self.assertIsInstance(azure_v2_result, pd.DataFrame)
        self.assertEqual(
            set(azure_v2_result.columns),
            {'category', 'service', 'resource', 'account', 'region', 'cost'}
        )
        self.assertEqual(azure_v2_result.columns[0], 'category')
        self.assertEqual(azure_v2_result['category'].iloc[0], 'product3')


if __name__ == '__main__':
    unittest.main() 