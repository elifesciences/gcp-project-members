#!/bin/bash
set -e
gcloud auth login --no-launch-browser
echo "fetching GCP members. this may take a minute."
python gcp_project_members.py > /tmp/iam-dump.txt
echo "wrote /tmp/iam-dump.txt"
rm -rf ./tmp

