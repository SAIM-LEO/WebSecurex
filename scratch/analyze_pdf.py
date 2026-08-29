import PyPDF2
import os

pdf_path = r"e:\WebSecureX.(2)\Documetation.pdf"
output_path = r"e:\WebSecureX.(2)\scratch\pdf_extract.txt"

os.makedirs(os.path.dirname(output_path), exist_ok=True)

try:
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        with open(output_path, "w", encoding="utf-8") as out:
            for i in range(min(15, len(reader.pages))):
                out.write(f"--- PAGE {i+1} ---\n")
                out.write(reader.pages[i].extract_text())
                out.write("\n\n")
    print("Extraction successful")
except Exception as e:
    print(f"Error: {e}")
