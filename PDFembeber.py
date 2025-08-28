import streamlit as st
from PyPDF2 import PdfWriter, PdfReader, PdfMerger
import io
import os
import time

def embed_files(main_pdf_data, files_to_embed, main_pdf_name, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Starting embed_files for {main_pdf_name}")
    try:
        pdf_writer = PdfWriter()
        pdf_reader = PdfReader(main_pdf_data)
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Read {len(pdf_reader.pages)} pages from main PDF")
        
        for page in pdf_reader.pages:
            pdf_writer.add_page(page)
        
        for file_data, file_name in files_to_embed:
            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Embedding file: {file_name}")
            file_data.seek(0)
            pdf_writer.add_attachment(file_name, file_data.read())
        
        base_name = os.path.splitext(main_pdf_name)[0]
        output_filename = f"{base_name}_EMBEDDED.pdf"
        
        output_buffer = io.BytesIO()
        pdf_writer.write(output_buffer)
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Embedded files, output file: {output_filename}")
        
        return output_buffer, output_filename
    except Exception as e:
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error in embed_files: {str(e)}")
        raise

def merge_pdfs(pdf_files, order, main_pdf_name, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Starting merge_pdfs for {main_pdf_name}")
    try:
        merger = PdfMerger()
        for idx in order:
            pdf_files[idx][0].seek(0)
            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merging file: {pdf_files[idx][1]}")
            merger.append(pdf_files[idx][0])
        
        base_name = os.path.splitext(main_pdf_name)[0]
        output_filename = f"{base_name}_MERGED.pdf"
        
        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merger.close()
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merged PDFs, output file: {output_filename}")
        
        return output_buffer, output_filename
    except Exception as e:
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error in merge_pdfs: {str(e)}")
汲

def process_task(task)

def main():
    st.title("PDF File Manager")
    
    # Initialize session state
    if 'tasks' not in st.session_state:
        st.session_state.tasks = []
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0
    if 'pdf_order' not in st.session_state:
        st.session_state.pdf_order = {}
    if 'debug_logs' not in st.session_state:
        st.session_state.debug_logs = []
    
    debug_logs = st.session_state.debug_logs
    debug_logs.append(f"[{time.strftime('%缓

    # Display pending tasks
    st.subheader("Pending Tasks")
    for i, task in enumerate(st.session_state.tasks):
        st.write(f"Task {i+1}: {task['operation']} - Main PDF: {task['main_pdf_name']}")
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Displaying {len(st.session_state.tasks)} tasks")
    
    # Process tasks
    if st.session_state.tasks and st.button("Process All Tasks"):
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Process All Tasks button clicked")
        with st.spinner("Processing tasks..."):
            for i, task in enumerate(st.session_state.tasks):
                try:
                    output_buffer, output_filename = process_task(task, debug_logs)
                    
                    st.download_button(
                        label=f"Download {output_filename}",
                        data=output_buffer.getvalue(),
                        file_name=output_filename,
                        mime="application/pdf",
                        key=f"download_{i}"
                    )
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Generated download for {output_filename}")
                    
                    if task['operation'] == "Embed files as attachments":
                        st.info("""
                        Embedded files can be accessed in PDF readers that support attachments:
                        - Adobe Acrobat Reader: View > Show/Hide > Navigation Panes > Attachments
                        - Other PDF readers: Look for a paperclip icon or attachments panel
                        """)
                    
                    st.success(f"Task {i+1} processed successfully!")
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Task {i+1} processed successfully")
                except Exception as e:
                    st.error(f"Error processing task {i+1}: {str(e)}")
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error processing task {i+1}: {str(e)}")
    
    # Clear tasks
    if st.session_state.tasks and st.button("Clear All Tasks"):
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Clear All Tasks button clicked")
        st.session_state.tasks = []
        st.session_state.form_key = 0
        st.session_state.pdf_order = {}
        st.session_state.debug_logs = []
        st.success("All tasks cleared!")
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] All tasks and logs cleared")

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
# - [original_filename]_EMBEDDED.pdf (when embedding files)
# - [original_filename]_MERGED.pdf (when merging PDFs)
