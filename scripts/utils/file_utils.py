import requests
from pathlib import Path
from typing import Optional, Union
import PyPDF2 # Make sure this is in requirements.txt
import shutil

def download_file(url: str, destination_path: Union[str, Path], timeout: int = 10) -> bool:
    """Downloads a file from a URL to a destination path."""
    dest_path = Path(destination_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists

    try:
        print(f"Attempting to download '{url}' to '{dest_path}'...")
        response = requests.get(url, stream=True, timeout=timeout, allow_redirects=True, headers={'User-Agent': 'KicadDesignAssistant/1.0'})
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        with open(dest_path, 'wb') as f:
            # Use shutil.copyfileobj for potentially large files
            shutil.copyfileobj(response.raw, f)
        print(f"Successfully downloaded '{url}'")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        # Clean up partial download if it exists
        if dest_path.exists():
            try:
                dest_path.unlink()
            except OSError:
                pass # Ignore errors during cleanup
        return False
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}")
        if dest_path.exists():
             try:
                 dest_path.unlink()
             except OSError:
                 pass
        return False

def extract_pdf_text(pdf_path: Union[str, Path]) -> Optional[str]:
    """Extracts text content from a PDF file."""
    pdf_file = Path(pdf_path)
    if not pdf_file.exists() or not pdf_file.is_file():
        print(f"Error: PDF file not found at '{pdf_file}'")
        return None

    text_content = ""
    try:
        with open(pdf_file, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)
            print(f"Extracting text from '{pdf_file.name}' ({num_pages} pages)...")
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text_content += page.extract_text() or "" # Add page text, handle None case
        print(f"Text extraction complete.")
        return text_content
    except PyPDF2.errors.PdfReadError as e:
        print(f"Error reading PDF file '{pdf_file}': {e}. File might be corrupted or password-protected.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during PDF text extraction: {e}")
        return None

if __name__ == '__main__':
    # Example Usage
    print("--- Testing file_utils ---")
    # Test download (replace with a real, small PDF URL if needed)
    # test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf" # Example URL
    # download_ok = download_file(test_url, "docs/datasheets/dummy_test.pdf")
    # print(f"Download test successful: {download_ok}")

    # Test PDF extraction (assuming dummy_test.pdf was downloaded or you place a test PDF)
    # test_pdf = Path("docs/datasheets/dummy_test.pdf")
    # if download_ok and test_pdf.exists():
    #     extracted = extract_pdf_text(test_pdf)
    #     if extracted:
    #         print("\nExtracted Text (first 200 chars):")
    #         print(extracted[:200] + "...")
    #     else:
    #         print("\nText extraction failed.")
    #     # Clean up test file
    #     # test_pdf.unlink()
    # else:
    #     print("\nSkipping text extraction test (download failed or file missing).")
    pass # Add actual test calls if desired

