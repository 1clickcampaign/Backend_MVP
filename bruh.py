import os

def check_file_encoding(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            file.read()
        return None
    except UnicodeDecodeError as e:
        return str(e)

def scan_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                error = check_file_encoding(filepath)
                if error:
                    print(f"Encoding issue in {filepath}: {error}")

if __name__ == "__main__":
    scan_directory('.')