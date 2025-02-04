import streamlit as st
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfWriter, PdfReader
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

def embed_files(main_pdf, files_to_embed):
    # Create PDF writer object
    pdf_writer = PdfWriter()

    # Add the main PDF pages
    pdf_reader = PdfReader(main_pdf)
    for page in pdf_reader.pages:
        pdf_writer.add_page(page)

    # Embed each file as an attachment
    for file in files_to_embed:
        file_data = file.read()
        filename = file.name
        pdf_writer.add_attachment(filename, file_data)

    return pdf_writer

def main():
    st.title("PDF Document and File Embedder")

    # File upload for DOCX
    docx_file = st.file_uploader("Upload DOCX file (will be converted to PDF)", type=['docx'])

    # Multiple file upload for embedding
    files_to_embed = st.file_uploader(
        "Upload files to embed (These will be embedded as attachments)",
        type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],  # Add more file types as needed
        accept_multiple_files=True
    )

    if st.button("Convert and Embed") and docx_file is not None:
        try:
            with st.spinner("Processing..."):
                # Convert DOCX to PDF
                temp_pdf = docx_to_pdf(docx_file.read())

                # Embed files
                pdf_writer = embed_files(temp_pdf, files_to_embed)

                # Save to bytes buffer
                output_buffer = io.BytesIO()
                pdf_writer.write(output_buffer)

                # Clean up temporary file
                os.unlink(temp_pdf)

                # Offer the PDF with embedded files for download
                st.download_button(
                    label="Download PDF with embedded files",
                    data=output_buffer.getvalue(),
                    file_name="document_with_attachments.pdf",
                    mime="application/pdf"
                )

                st.success("Files have been converted and embedded successfully!")

                st.info("""
                Note: The embedded files can be accessed in PDF readers that support attachments:
                - Adobe Acrobat Reader: View > Show/Hide > Navigation Panes > Attachments
                - Other PDF readers: Look for a paperclip icon or attachments panel
                """)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
# - temporary PDF file (automatically deleted after processing)
# - document_with_attachments.pdf (downloaded by user)
