#!/bin/bash
python3 -m pytest tests/ --ignore=tests/tests -v --tb=line 2>&1 | tail -120
