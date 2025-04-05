#!/usr/bin/env bash

trap : TERM INT; (while true; do sleep 1000; done) & wait
