import streamlit as st
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfMerger
import io
import tempfile
import os

def docx_to_pdf(docx_content):
    # Create a temporary PDF file
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')

    # Convert DOCX content to text
    doc = Document(io.BytesIO(docx_content))
    text_content = []
    for para in doc.paragraphs:
        text_content.append(para.text)

    # Create PDF
    c = canvas.Canvas(temp_pdf.name, pagesize=letter)
    y = 750  # Starting y position
    for line in text_content:
        if y < 50:  # Check if we need a new page
            c.showPage()
            y = 750
        c.drawString(50, y, line)
        y -= 15
    c.save()

    return temp_pdf.name

def main():
    st.title("Document Converter and Merger")

    # File upload for DOCX
    docx_file = st.file_uploader("Upload DOCX file", type=['docx'])

    # Multiple PDF file upload
    pdf_files = st.file_uploader("Upload PDF files to embed", type=['pdf'], accept_multiple_files=True)

    if st.button("Convert and Merge") and docx_file is not None:
        try:
            with st.spinner("Processing..."):
                # Convert DOCX to PDF
                temp_pdf = docx_to_pdf(docx_file.read())

                # Create PDF merger object
                merger = PdfMerger()

                # Add converted PDF
                merger.append(temp_pdf)

                # Add selected PDFs
                for pdf in pdf_files:
                    merger.append(pdf)

                # Create output PDF in memory
                output = io.BytesIO()
                merger.write(output)
                merger.close()

                # Clean up temporary file
                os.unlink(temp_pdf)

                # Offer the merged PDF for download
                st.download_button(
                    label="Download merged PDF",
                    data=output.getvalue(),
                    file_name="merged_document.pdf",
                    mime="application/pdf"
                )

                st.success("Files have been converted and merged successfully!")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
# - temporary PDF file (automatically deleted after processing)
# - merged_document.pdf (downloaded by user)
