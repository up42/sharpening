#!/bin/bash

python -m pytest --pylint --pylint-rcfile=../../pylintrc --mypy --mypy-ignore-missing-imports --cov=src/