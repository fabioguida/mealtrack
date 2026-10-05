#!/bin/bash
# EC2 user data: runs once at first boot. Only the bare minimum; deploy/setup.sh does the rest.
apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q git curl unzip
mkdir -p /srv/mealtrack
