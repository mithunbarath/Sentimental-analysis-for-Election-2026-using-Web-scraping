import os
import glob

files = glob.glob("**/*.py", recursive=True)

for file in files:
    if "models.py" in file or "filters.py" in file or "exporter.py" in file or "main.py" in file:
        continue # Already fixed these

    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        if "is_palladam_related" in content:
            print(f"Fixing {file}")
            new_content = content.replace("is_palladam_related", "is_kongu_related")
            with open(file, "w", encoding="utf-8") as f:
                f.write(new_content)
    except Exception as e:
        print(f"Could not process {file}: {e}")

print("Fix applied.")
