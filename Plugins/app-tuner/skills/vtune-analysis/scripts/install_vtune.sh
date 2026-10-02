#!/bin/bash
# Install Intel VTune from the oneAPI apt repo. Idempotent.
set -euo pipefail
if command -v vtune >/dev/null 2>&1 || ls /opt/intel/oneapi/vtune/*/bin64/vtune >/dev/null 2>&1; then
  echo "vtune already installed"
  exit 0
fi
sudo -n mkdir -p /usr/share/keyrings
tmp=$(mktemp)
curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -o "$tmp"
gpg --dearmor < "$tmp" | sudo -n tee /usr/share/keyrings/oneapi-archive-keyring.gpg >/dev/null
rm -f "$tmp"
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
  | sudo -n tee /etc/apt/sources.list.d/oneAPI.list >/dev/null
sudo -n apt-get update
sudo -n apt-get install -y intel-oneapi-vtune
echo "installed"
