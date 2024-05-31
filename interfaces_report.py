"""
This script extracts the Interfaces information from the Inventory > Interfaces table,
and use it to generate a report to show the interfaces capacity per device.
"""

import argparse
import csv
import datetime
import os

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from ipfabric import IPFClient

# List of reasons for an interface to be admin down
INTERFACE_ADMIN_DOWN_REASON = [
    "admin",
    "admin-down",
    "parent-admin-down",
    "disable",
    "disabled",
]

# regex to match logical interfaces, or interfaces to exclude from this report
EXCLUDE_INTF_NAME = (
    "^(ae|bond|dock|ifb|lo|lxc|mgm|npu\d+_vl|oob|po|ssl|tep|tu|ucse|unb|veth|virtu|vl|vxl|wan|\/Common\/)|\.\d+"
)


def argument_parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Script to create a report showing the interfaces status per device")

    parser.add_argument(
        "-c",
        "--csv",
        help="Format the output as a CSV file, only containing the interfaces report",
        action="store_true",
    )
    parser.add_argument(
        "-x",
        "--xlsx",
        help="[Default] Format the output as an Excel file, containing the interfaces report and raw data",
        action="store_true",
    )

    return parser.parse_args()


def create_report_file(
    interfaces_report: list,
    interfaces_json: list,
    report_format: str,
    report_output: str,
) -> str:
    """
    Create a report file with the given format.

    Args:
        report_format (str): The format of the report file to create.
        report_output (str): The name of the report file to create.
        interfaces_report (list): The list of interfaces report data.

    """
    if report_format == "csv":
        report_file = f"{report_output}.csv"
        with open(report_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=interfaces_report[0].keys())
            writer.writeheader()
            for item in interfaces_report:
                writer.writerow(item)
    elif report_format == "xlsx":
        report_file = f"{report_output}.xlsx"
        df_intf_report = pd.DataFrame(interfaces_report)
        df_intf_raw = pd.DataFrame(interfaces_json)
        with pd.ExcelWriter(report_file) as writer:
            df_intf_report.to_excel(writer, sheet_name="report", index=False)
            df_intf_raw.to_excel(writer, sheet_name="intf_raw_data", index=False)

    return report_file


def fetch_interfaces_data(ipf: IPFClient) -> dict:
    """
    Creates a dictionary of interfaces data for each hostname from the IPFClient.

    Args:
        ipf: IPFClient instance to retrieve interfaces data.

    Returns:
        A dictionary containing interfaces data grouped by hostname, and a list of all interfaces data.
    """

    # Filter to exclude logical interfaces, using insensitive regex match
    filter_exclude_interfaces = {"intName": ["nireg", EXCLUDE_INTF_NAME]}

    intf_columns = [
        "hostname",
        "sn",
        "intName",
        "siteName",
        "l1",
        "l2",
        "reason",
        "dscr",
        "mac",
        "duplex",
        "speed",
        "bandwidth",
        "speedValue",
        "speedType",
        "media",
        "errDisabled",
        "mtu",
        "primaryIp",
        "hasTransceiver",
        "transceiverType",
    ]

    number_of_interfaces = ipf.inventory.interfaces.count(filters=filter_exclude_interfaces)
    print(f" for {number_of_interfaces} interfaces)", end="", flush=True)

    interfaces_json = ipf.inventory.interfaces.all(columns=intf_columns, filters=filter_exclude_interfaces)

    interfaces_dict = {}
    for intf in interfaces_json:
        if intf["hostname"] in interfaces_dict:
            interfaces_dict[intf["hostname"]]["interfaces"].append(intf)
        else:
            interfaces_dict[intf["hostname"]] = {"interfaces": [intf]}

    return interfaces_dict, interfaces_json


def build_interface_report(interfaces_dict: dict) -> list:
    # sourcery skip: use-assigned-variable
    """
    Builds a report based on the interfaces data provided in the interfaces_dict.

    Args:
        interfaces_dict: A dictionary containing interfaces data grouped by hostname.

    Returns:
        A list of dictionaries representing the interface report for each hostname.
    """

    interfaces_report = []
    for hostname, data in interfaces_dict.items():
        interfaces_total = len(data["interfaces"])
        interfaces_l1up_l2up = len([i for i in data["interfaces"] if i["l1"] == "up" and i["l2"] == "up"])
        interfaces_l1down_l2down = len([i for i in data["interfaces"] if i["l1"] == "down" and i["l2"] == "down"])
        interfaces_l1up_l2down = len([i for i in data["interfaces"] if i["l1"] == "up" and i["l2"] == "down"])
        interfaces_l1l2unknown = len(
            [i for i in data["interfaces"] if i["l1"] not in ["up", "down"] or i["l2"] not in ["up", "down"]]
        )
        interfaces_admin_down = len([i for i in data["interfaces"] if i["reason"] in INTERFACE_ADMIN_DOWN_REASON])
        interfaces_err_disabled = len(
            [i for i in data["interfaces"] if i.get("reason") is not None and "err" in i.get("reason", "")]
        )

        count_interfaces_in_use = interfaces_l1up_l2up + interfaces_l1up_l2down + interfaces_l1l2unknown
        count_interfaces_not_used = interfaces_l1down_l2down  # admin_down and err_disabled are already l1&l2 down

        interfaces_report.append(
            {
                "hostname": hostname,
                "sn": data["interfaces"][0]["sn"],
                "siteName": data["interfaces"][0]["siteName"],
                "total": interfaces_total,
                "l1&l2 up": interfaces_l1up_l2up,
                "l1&l2 down": interfaces_l1down_l2down,
                "l1 up & l2 down": interfaces_l1up_l2down,
                "l1 and l2 unknown": interfaces_l1l2unknown,
                "admin-down": interfaces_admin_down,
                "err-disabled": interfaces_err_disabled,
                "port utilisation (%)": round((count_interfaces_in_use / interfaces_total) * 100, 2)
                if interfaces_total > 0
                else 0,
                "port availability (%)": round((count_interfaces_not_used / interfaces_total) * 100, 2)
                if interfaces_total > 0
                else 0,
            }
        )
    return interfaces_report


def main():
    """
    Main function to generate the interfaces report.
    """
    # Load the environment variables and parse the arguments
    load_dotenv(find_dotenv(), override=True)
    args = argument_parser()
    report_format = "csv" if args.csv else "xlsx"

    # creates variables from the environment variables
    ipf_url = os.getenv("IPF_URL_TS")
    ipf_auth = os.getenv("IPF_TOKEN_TS")
    ipf_verify = eval(os.getenv("IPF_VERIFY", "False").title())
    report_output = os.getenv("REPORT_OUTPUT", "devices_interface_report")
    ipf_snapshot = "$last"

    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Generate the filename with the timestamp at the beginning
    report_output = f"{timestamp}-interfaces_report"

    # Create an IPFClient object
    ipf = IPFClient(base_url=ipf_url, auth=ipf_auth, snapshot_id=ipf_snapshot, verify=ipf_verify)

    print("Fetching data", end="", flush=True)
    interfaces_dict, interfaces_json = fetch_interfaces_data(ipf)
    print(f"\r✅ Done - Fetching data for {len(interfaces_json)} interfaces")

    print("Processing interfaces data to build the report", end="", flush=True)
    interfaces_report = build_interface_report(interfaces_dict)
    print("\r✅ Done - Processing interfaces data to build the report", end="", flush=True)

    print("Generating Report...")
    report_file = create_report_file(
        interfaces_report=interfaces_report,
        interfaces_json=interfaces_json,
        report_format=report_format,
        report_output=report_output,
    )
    print(f"\r✅ Done - Generating Report, saved to `{report_file}`")


if __name__ == "__main__":
    main()
