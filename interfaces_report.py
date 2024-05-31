"""
This script extracts the Interfaces information from the Inventory > Interfaces table,
and use it to generate a report to show the interfaces capacity per device.
"""

import csv
import datetime
import os

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

load_dotenv(find_dotenv(), override=True)


# Get the path to the script's directory
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
print(f"Fetching data for {number_of_interfaces} interfaces...", end="", flush=True)

interfaces_json = ipf.inventory.interfaces.all(columns=intf_columns, filters=filter_exclude_interfaces)

print(
    f"\r✅ Done - Fetching data for {number_of_interfaces} interfaces\nProcessing interfaces data...",
    end="",
    flush=True,
)
interfaces_dict = {}
for intf in interfaces_json:
    if intf["hostname"] in interfaces_dict:
        interfaces_dict[intf["hostname"]]["interfaces"].append(intf)
    else:
        interfaces_dict[intf["hostname"]] = {"interfaces": [intf]}

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

    sum_interfaces_used = interfaces_l1up_l2up + interfaces_l1l2unknown + interfaces_l1up_l2down
    sum_interfaces_unused = interfaces_l1down_l2down  # admin_down and err_disabled are already l1&l2 down
    interfaces_report.append(
        {
            "hostname": hostname,
            "sn": data["interfaces"][0]["sn"],
            "siteName": data["interfaces"][0]["siteName"],
            "total": interfaces_total,
            "l1&l2 up": interfaces_l1up_l2up,
            "l1&l2 down": interfaces_l1down_l2down,
            "l1 up & l2 down": interfaces_l1up_l2down,
            "L1 and l2 unknown": interfaces_l1l2unknown,
            "admin-down": interfaces_admin_down,
            "err-disabled": interfaces_err_disabled,
            "port utilisation (%)": round((sum_interfaces_used / interfaces_total) * 100, 2)
            if interfaces_total > 0
            else 0,
            "port availability (%)": round((sum_interfaces_unused / interfaces_total) * 100, 2)
            if interfaces_total > 0
            else 0,
        }
    )

print("\r✅ Done - Processing interfaces data\nGenerating Excel Report...", end="", flush=True)

# Generate an excel file with the interfaces report
import pandas as pd

df_intf_report = pd.DataFrame(interfaces_report)
df_intf_raw = pd.DataFrame(interfaces_json)
with pd.ExcelWriter(f"{report_output}.xlsx") as writer:
    df_intf_report.to_excel(writer, sheet_name="report", index=False)
    df_intf_raw.to_excel(writer, sheet_name="intf_raw_data", index=False)
print(f"\r✅ Done - Generating Excel Report, saved to `{report_output}.xlsx`")

# # Export the data to a CSV file
# print("Generating CSV Report...", end="", flush=True)
# with open(f"{report_output}.csv", "w", newline="") as csvfile:
#     writer = csv.DictWriter(csvfile, fieldnames=interfaces_report[0].keys())
#     writer.writeheader()
#     for item in interfaces_report:
#         writer.writerow(item)
# print(f"\r✅ Done - Generating CSV report, saved to `{report_output}.csv`")
