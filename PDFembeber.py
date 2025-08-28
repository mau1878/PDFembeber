import streamlit as st
from PyPDF2 import PdfWriter, PdfReader, PdfMerger
import io
import os

def embed_files(main_pdf, files_to_embed, main_pdf_name):
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

    # Create output filename with _EMBEDDED suffix
    base_name = os.path.splitext(main_pdf_name)[0]
    output_filename = f"{base_name}_EMBEDDED.pdf"
    
    # Save to bytes buffer
    output_buffer = io.BytesIO()
    pdf_writer.write(output_buffer)
    
    return output_buffer, output_filename

def merge_pdfs(pdf_files, order, main_pdf_name):
    merger = PdfMerger()

    # Add PDFs in the specified order
    for idx in order:
        pdf_files[idx].seek(0)  # Reset file pointer
        merger.append(pdf_files[idx])

    # Create output filename with _MERGED suffix
    base_name = os.path.splitext(main_pdf_name)[0]
    output_filename = f"{base_name}_MERGED.pdf"
    
    output_buffer = io.BytesIO()
    merger.write(output_buffer)
    merger.close()

    return output_buffer, output_filename

def process_task(main_pdf, additional_files, operation, order=None):
    if operation == "Embed files as attachments":
        output_buffer, output_filename = embed_files(main_pdf, additional_files, main_pdf.name)
        return output_buffer, output_filename
    else:  # Merge PDFs
        all_pdfs = [main_pdf] + additional_files
        output_buffer, output_filename = merge_pdfs(all_pdfs, order, main_pdf.name)
        return output_buffer, output_filename

def main():
    st.title("PDF File Manager")

    # Initialize session state for tasks
    if 'tasks' not in st.session_state:
        st.session_state.tasks = []

    # File upload section
    with st.form("pdf_form"):
        main_pdf = st.file_uploader("Upload main PDF file", type=['pdf'], key="main_pdf")
        
        operation = st.radio(
            "Choose operation:",
            ["Embed files as attachments", "Merge PDFs"],
            key="operation"
        )

        if operation == "Embed files as attachments":
            additional_files = st.file_uploader(
                "Upload files to embed (These will be attached)",
                type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],
                accept_multiple_files=True,
                key="embed_files"
            )
        else:
            additional_files = st.file_uploader(
                "Upload PDFs to merge",
                type=['pdf'],
                accept_multiple_files=True,
                key="merge_files"
            )

            if additional_files:
                # Create ordering interface
                all_pdfs = [main_pdf] + additional_files if main_pdf else additional_files
                pdf_names = [main_pdf.name] + [pdf.name for pdf in additional_files] if main_pdf else [pdf.name for pdf in additional_files]
                
                st.write("Arrange the order of PDFs (drag to reorder):")
                order = st.session_state.get('pdf_order', list(range(len(all_pdfs))))
                
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
                
                # Sort the order to handle duplicate positions
                final_order = sorted(range(len(order)), key=lambda k: order[k])
            else:
                final_order = [0]

        submit = st.form_submit_button("Add Task")

        if submit and main_pdf and additional_files:
            st.session_state.tasks.append({
                'main_pdf': main_pdf,
                'additional_files': additional_files,
                'operation': operation,
                'order': final_order if operation == "Merge PDFs" else None
            })
            st.success("Task added successfully!")

    # Process all tasks
    if st.button("Process All Tasks") and st.session_state.tasks:
        with st.spinner("Processing all tasks..."):
            for i, task in enumerate(st.session_state.tasks):
                try:
                    output_buffer, output_filename = process_task(
                        task['main_pdf'],
                        task['additional_files'],
                        task['operation'],
                        task['order']
                    )

                    st.download_button(
                        label=f"Download {output_filename}",
                        data=output_buffer.getvalue(),
                        file_name=output_filename,
                        mime="application/pdf",
                        key=f"download_{i}"
                    )

                    if task['operation'] == "Embed files as attachments":
                        st.info("""
                        Note: The embedded files can be accessed in PDF readers that support attachments:
                        - Adobe Acrobat Reader: View > Show/Hide > Navigation Panes > Attachments
                        - Other PDF readers: Look for a paperclip icon or attachments panel
                        """)

                    st.success(f"Task {i+1} processed successfully!")

                except Exception as e:
                    st.error(f"Error in task {i+1}: {str(e)}")

    # Clear tasks button
    if st.button("Clear All Tasks"):
        st.session_state.tasks = []
        st.success("All tasks cleared!")

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
# - [original_filename]_EMBEDDED.pdf (when embedding files)
# - [original_filename]_MERGED.pdf (when merging PDFs)
