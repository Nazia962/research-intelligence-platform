"""Create a Pro licence key for a paying customer.

Usage:
    python make_license.py "Customer name" --days 30

Send the printed key to the customer (e.g. by email after they pay).
It needs LICENSE_SECRET in your .env file - use the same value on your server.
"""
import argparse

from services.license_service import make_key, verify_key

parser = argparse.ArgumentParser(description="Generate a Research Intelligence Platform Pro key")
parser.add_argument("customer", help="customer name or id (letters/numbers)")
parser.add_argument("--days", type=int, default=30, help="how many days the key stays valid (default 30)")
args = parser.parse_args()

key = make_key(args.customer, args.days)
ok, message, _ = verify_key(key)
print(f"\nLicence key: {key}\n{message}\n")
