import os
import sys
import django

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qubix_project.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
django.setup()

from django.core.management import call_command

# Dump data
with open('working_data.json', 'w', encoding='utf-8') as f:
    call_command('dumpdata', natural_foreign=True, stdout=f)

print("Done! Created working_data.json")