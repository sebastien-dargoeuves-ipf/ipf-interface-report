# Interfaces Report

This script generates a report on network interfaces. It excludes certain types of interfaces based on a regular expression.

## Requirements

- Python 3.9 or higher
- The script uses environment variables for configuration. These can be set in a `.env` file.

## Environment Variables

The script uses the following environment variables:

- `IPF_URL`: The URL of the IP Fabric instance.
- `IPF_TOKEN`: The authentication token for IP Fabric.
- `IPF_VERIFY`: Whether to verify the SSL certificate of the IP Fabric instance. This should be a boolean value (`True` or `False`). Default is `False`.
- `REPORT_OUTPUT`: The name of the output CSV file. Default is `devices_interface_report.csv`.

## Usage

You can run the script with no arguments:

```shell
python interfaces_report.py
```

## Output

The script outputs an Excel file with the report. The first sheet contains the report, with the % calculated, whereas the 2nd sheet, is the raw interface export from IP Fabric,  with the same filter applied. So excluded interfaces, will not appear in this file.

The filename is generated by appending the current timestamp and `-interfaces_report.csv` to the `REPORT_OUTPUT` environment variable.

For example, if `REPORT_OUTPUT` is `devices_interface_report.csv` and the current timestamp is `2022-01-01_12-00-00`, the output filename would be `2022-01-01_12-00-00-interfaces_report.csv`.
