# export_data.py
import os
import sys
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qubix_project.settings')

import django
django.setup()

from django.core.management import call_command
from django.core import serializers
from io import StringIO

# Create a StringIO buffer to capture output
out = StringIO()

# Call dumpdata with UTF-8 handling
call_command('dumpdata', 
    exclude=['contenttypes', 'auth.permission'],
    indent=2,
    stdout=out,
    use_base_manager=False
)

# Write to file with UTF-8 encoding
with open('data.json', 'w', encoding='utf-8') as f:
    f.write(out.getvalue())

print("✅ Data exported successfully to data.json")