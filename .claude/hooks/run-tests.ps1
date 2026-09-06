Set-Location (git rev-parse --show-toplevel)
python -m unittest discover -s tests 2>&1 | Select-Object -Last 5