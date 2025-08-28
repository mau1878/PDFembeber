import streamlit as st
from PyPDF2 import PdfWriter, PdfReader, PdfMerger
import io
import os
import time

# No changes needed in these helper functions
def embed_files(main_pdf_data, files_to_embed, main_pdf_name, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Starting embed_files for {main_pdf_name}")
    try:
        pdf_writer = PdfWriter()
        # Ensure buffer is at the start
        main_pdf_data.seek(0)
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

def merge_pdfs(pdf_files_data, main_pdf_name, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Starting merge_pdfs for {main_pdf_name}")
    try:
        merger = PdfMerger()
        for pdf_data, pdf_name in pdf_files_data:
            pdf_data.seek(0)
            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merging file: {pdf_name}")
            merger.append(pdf_data)

        base_name = os.path.splitext(main_pdf_name)[0]
        output_filename = f"{base_name}_MERGED.pdf"

        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merger.close()
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merged PDFs, output file: {output_filename}")

        return output_buffer, output_filename
    except Exception as e:
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error in merge_pdfs: {str(e)}")
        raise

def process_task(task, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Processing task: {task['operation']} for {task['main_pdf_name']}")
    try:
        if task['operation'] == "Embed files as attachments":
            return embed_files(task['main_pdf_data'], task['additional_files'], task['main_pdf_name'], debug_logs)
        else: # "Merge PDFs"
            return merge_pdfs(task['ordered_pdfs'], task['main_pdf_name'], debug_logs)
    except Exception as e:
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error processing task: {str(e)}")
        raise

def main():
    st.title("PDF File Manager 🚀")

    # Initialize session state
    if 'tasks' not in st.session_state:
        st.session_state.tasks = []
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0
    if 'debug_logs' not in st.session_state:
        st.session_state.debug_logs = []

    debug_logs = st.session_state.debug_logs

    # Task input section
    st.header("1. Add New Task")

    with st.form(key=f"pdf_form_{st.session_state.form_key}", clear_on_submit=True):
        main_pdf = st.file_uploader("Upload Main PDF File", type=['pdf'])
        
        operation = st.radio(
            "Choose Operation:",
            ["Embed files as attachments", "Merge PDFs"],
            horizontal=True
        )
        
        additional_files_uploader = None
        ordered_pdf_names = None

        if operation == "Embed files as attachments":
            additional_files_uploader = st.file_uploader(
                "Upload Files to Embed (optional)",
                type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],
                accept_multiple_files=True
            )
        else: # "Merge PDFs"
            additional_files_uploader = st.file_uploader(
                "Upload Additional PDFs to Merge (required)",
                type=['pdf'],
                accept_multiple_files=True
            )
            
            if main_pdf and additional_files_uploader:
                pdf_names = [main_pdf.name] + [f.name for f in additional_files_uploader]
                # Use st.multiselect for intuitive ordering
                ordered_pdf_names = st.multiselect(
                    "Arrange merge order (click to select/reorder):",
                    options=pdf_names,
                    default=pdf_names # Pre-select all in their original order
                )

        submit_button = st.form_submit_button("➕ Add Task to Queue")

        if submit_button:
            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Add Task button clicked")
            if not main_pdf:
                st.error("Please upload a main PDF file.")
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error: No main PDF uploaded")
            elif operation == "Merge PDFs" and not additional_files_uploader:
                st.error("Please upload at least one additional PDF for merging.")
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error: No additional PDFs for merging")
            else:
                try:
                    main_pdf_data = io.BytesIO(main_pdf.read())
                    additional_files_data = [(io.BytesIO(f.read()), f.name) for f in additional_files_uploader] if additional_files_uploader else []
                    
                    new_task = {
                        'main_pdf_data': main_pdf_data,
                        'main_pdf_name': main_pdf.name,
                        'operation': operation,
                        'additional_files': additional_files_data,
                        'ordered_pdfs': None # For merge task
                    }

                    if operation == "Merge PDFs":
                        # Create a map of name -> data for easy lookup
                        all_pdfs_map = {name: data for data, name in [(main_pdf_data, main_pdf.name)] + additional_files_data}
                        
                        # Build the final ordered list of (data, name) tuples
                        final_ordered_pdfs = []
                        for name in ordered_pdf_names:
                            final_ordered_pdfs.append((all_pdfs_map[name], name))
                        
                        new_task['ordered_pdfs'] = final_ordered_pdfs
                        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merge order set: {ordered_pdf_names}")
                    
                    st.session_state.tasks.append(new_task)
                    st.success("Task added to the queue below!")
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Task added, total tasks: {len(st.session_state.tasks)}")
                    
                    # Instead of incrementing form_key, clear_on_submit=True handles the reset
                    # No need to manage form_key manually anymore for resetting purposes
                    
                except Exception as e:
                    st.error(f"Failed to add task: {e}")
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error adding task: {e}")

    # Display pending tasks and process
    if st.session_state.tasks:
        st.header("2. Process Task Queue")
        
        for i, task in enumerate(st.session_state.tasks):
            st.write(f"**Task {i+1}:** {task['operation']} on '{task['main_pdf_name']}'")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Process All Tasks", use_container_width=True, type="primary"):
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Process All Tasks button clicked")
                with st.spinner("Processing..."):
                    for i, task in enumerate(st.session_state.tasks):
                        try:
                            output_buffer, output_filename = process_task(task, debug_logs)
                            
                            st.download_button(
                                label=f"Download '{output_filename}'",
                                data=output_buffer.getvalue(),
                                file_name=output_filename,
                                mime="application/pdf",
                                key=f"download_{i}"
                            )
                            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Generated download for {output_filename}")
                        except Exception as e:
                            st.error(f"Error processing task {i+1}: {e}")
                            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error processing task {i+1}: {e}")
                st.success("All tasks processed!")

        with col2:
            if st.button("❌ Clear All Tasks", use_container_width=True):
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Clear All Tasks button clicked")
                st.session_state.tasks = []
                st.session_state.debug_logs = [] # Also clear logs
                st.rerun() # Rerun to update the display immediately
    
    # Debug log display
    st.subheader("Debug Logs")
    with st.expander("View Debug Logs"):
        # Display logs in reverse chronological order
        st.text_area("", value="\n".join(reversed(debug_logs)), height=200, key="debug_log_area")

if __name__ == "__main__":
    main()
