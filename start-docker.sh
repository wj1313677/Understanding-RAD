#!/bin/bash
# Wrapper script to run docker-start.sh from project root

cd "$(dirname "$0")/docker"
./docker-start.sh
