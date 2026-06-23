#!/usr/bin/env bash
set -euo pipefail

# gen_license.sh — issue a signed scmap license certificate for a customer.
#
# Usage:
#   ./gen_license.sh "Customer Name" "customer@email.com" [days_valid]
#
# The output is written to ./scmap-<customer>-<date>.crt.
# Deliver this file to the customer; they place it at:
#   ~/.seiscomp/licenses/scmap.crt
# or:
#   ~/seiscomp/share/licenses/scmap.crt
#
# The CA key (scmap-ca-key.pem) must be in the same directory as this script,
# kept secret.  The CA cert (scmap-ca-cert.pem) is public and embedded in
# scmap.py.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CA_DIR="$(dirname "$SCRIPT_DIR")/certs"
CA_KEY="$CA_DIR/scmap-ca-key.pem"
CA_CERT="$CA_DIR/scmap-ca-cert.pem"
DAYS="${3:-365}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 \"Customer Name\" \"customer@email.com\" [days_valid]"
    echo ""
    echo "Generates a signed license certificate for the given customer."
    echo "The CA must have been initialised first via init_ca.sh."
    exit 1
fi

CUSTOMER="$1"
EMAIL="$2"
CERT_FILE="scmap-${CUSTOMER// /_}-$(date +%F).crt"

if [ ! -f "$CA_KEY" ] || [ ! -f "$CA_CERT" ]; then
    echo "ERROR: CA key or cert not found in $CA_DIR"
    echo "Run init_ca.sh first."
    exit 1
fi

echo "=== Issuing license for: $CUSTOMER <$EMAIL> ==="

# Create temp CSR and key (discarded after signing)
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

CUSTOMER_KEY="$TMPDIR/customer-key.pem"
CUSTOMER_REQ="$TMPDIR/customer-req.pem"

openssl req -newkey rsa:2048 -nodes \
    -keyout "$CUSTOMER_KEY" \
    -out "$CUSTOMER_REQ" \
    -subj "/CN=${CUSTOMER}/emailAddress=${EMAIL}" 2>/dev/null

# Sign with the CA passing publication rights as a custom extension
openssl x509 -req -days "$DAYS" \
    -in "$CUSTOMER_REQ" \
    -CA "$CA_CERT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -extfile <(printf "1.2.3.4.5.6.7.8=ASN1:UTF8String:publication=true;updatesUntil=$(date -d "+$DAYS days" '+%Y-%m-%d')") \
    -out "$CERT_FILE" 2>/dev/null

echo "License written to: $CERT_FILE"
echo ""
echo "Deliver this file to the customer as 'scmap.crt'."
echo "They install it at: ~/.seiscomp/licenses/scmap.crt"
echo "                or: ~/seiscomp/share/licenses/scmap.crt"
