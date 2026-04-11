import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qubix_project.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.core.management import call_command

with open('clean_data.json', 'w', encoding='utf-8') as f:
    call_command('dumpdata', 
                 natural_foreign=True,
                 exclude=['contenttypes', 'auth.permission'],
                 stdout=f)

print("Created clean_data.json without contenttypes")