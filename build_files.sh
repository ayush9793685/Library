#!/bin/bash
set -e

# Vercel's build image has a managed system Python, so install into a throwaway venv.
if command -v uv >/dev/null 2>&1; then
  uv venv /tmp/buildenv --python 3.12
  uv pip install --python /tmp/buildenv/bin/python -r requirements.txt
else
  python3 -m venv /tmp/buildenv
  /tmp/buildenv/bin/pip install -r requirements.txt
fi

<<<<<<< HEAD
/tmp/buildenv/bin/python manage.py collectstatic --noinput
=======
/tmp/buildenv/bin/python manage.py collectstatic --noinput
>>>>>>> 49724e3896a26d59b87f5e59d7db23406a394769
