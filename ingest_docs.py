import os
from pypdf import PdfReader
from storage import init_db, store_document_chunk

def ingest_file(file_path):
    init_db()
    filename = os.path.basename(file_path)
    text = ""
    
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() + " "
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

    # Split text into manageable chunks (approx 1000 chars) for the LLM
    chunks = [text[i:i+1000] for i in range(0, len(text), 800)]
    for chunk in chunks:
        store_document_chunk(filename, chunk.strip())
    
    print(f"Successfully ingested {len(chunks)} sections from {filename}.")

if __name__ == "__main__":
    path = input("Enter path to PDF or TXT file to teach Kora: ").strip('"')
    if os.path.exists(path):
        ingest_file(path)
    else:
        print("File not found.")