import streamlit as st
from PyPDF2 import PdfWriter, PdfReader, PdfMerger
import io
import tempfile

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

def merge_pdfs(pdf_files, order):
    merger = PdfMerger()

    # Add PDFs in the specified order
    for idx in order:
        pdf_files[idx].seek(0)  # Reset file pointer
        merger.append(pdf_files[idx])

    output_buffer = io.BytesIO()
    merger.write(output_buffer)
    merger.close()

    return output_buffer

def main():
    st.title("PDF File Manager")

    # Main PDF file upload
    main_pdf = st.file_uploader("Upload main PDF file", type=['pdf'])

    if main_pdf is not None:
        # Choose operation
        operation = st.radio(
            "Choose operation:",
            ["Embed files as attachments", "Merge PDFs"]
        )

        if operation == "Embed files as attachments":
            # Multiple file upload for embedding
            files_to_embed = st.file_uploader(
                "Upload files to embed (These will be embedded as attachments)",
                type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],
                accept_multiple_files=True
            )

            if st.button("Embed Files") and files_to_embed:
                try:
                    with st.spinner("Processing..."):
                        # Embed files
                        pdf_writer = embed_files(main_pdf, files_to_embed)

                        # Save to bytes buffer
                        output_buffer = io.BytesIO()
                        pdf_writer.write(output_buffer)

                        # Offer the PDF with embedded files for download
                        st.download_button(
                            label="Download PDF with embedded files",
                            data=output_buffer.getvalue(),
                            file_name="document_with_attachments.pdf",
                            mime="application/pdf"
                        )

                        st.success("Files have been embedded successfully!")

                        st.info("""
                        Note: The embedded files can be accessed in PDF readers that support attachments:
                        - Adobe Acrobat Reader: View > Show/Hide > Navigation Panes > Attachments
                        - Other PDF readers: Look for a paperclip icon or attachments panel
                        """)

                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

        else:  # Merge PDFs
            # Multiple PDF file upload for merging
            additional_pdfs = st.file_uploader(
                "Upload PDFs to merge",
                type=['pdf'],
                accept_multiple_files=True
            )

            if additional_pdfs:
                # Combine all PDFs into one list
                all_pdfs = [main_pdf] + additional_pdfs

                # Create a list of PDF names for ordering
                pdf_names = [main_pdf.name] + [pdf.name for pdf in additional_pdfs]

                # Create ordering interface
                st.write("Arrange the order of PDFs (drag to reorder):")
                order = st.session_state.get('pdf_order', list(range(len(all_pdfs))))

                # Create columns for ordering
                cols = st.columns(len(all_pdfs))
                for i, col in enumerate(cols):
                    with col:
                        new_pos = st.number_input(
                            pdf_names[i],
                            min_value=1,
                            max_value=len(all_pdfs),
                            value=order[i]+1,
                            key=f"pdf_{i}"
                        ) - 1
                        order[i] = new_pos

                # Sort the order to handle any duplicate positions
                final_order = sorted(range(len(order)), key=lambda k: order[k])

                if st.button("Merge PDFs"):
                    try:
                        with st.spinner("Processing..."):
                            # Merge PDFs
                            output_buffer = merge_pdfs(all_pdfs, final_order)

                            # Offer the merged PDF for download
                            st.download_button(
                                label="Download merged PDF",
                                data=output_buffer.getvalue(),
                                file_name="merged_document.pdf",
                                mime="application/pdf"
                            )

                            st.success("PDFs have been merged successfully!")

                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
# - document_with_attachments.pdf (when embedding files)
# - merged_document.pdf (when merging PDFs)
