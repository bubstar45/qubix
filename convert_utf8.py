with open('data.json', 'rb') as f:
    content = f.read()

with open('data_utf8.json', 'w', encoding='utf-8') as f:
    f.write(content.decode('utf-8', errors='ignore'))

print("File created: data_utf8.json")