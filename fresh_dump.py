import os
import sys
from django.core.management import call_command

# Set UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

# Dump data
with open('fresh_data.json', 'w', encoding='utf-8') as f:
    call_command('dumpdata', natural_foreign=True, stdout=f)

print("Done! Created fresh_data.json")