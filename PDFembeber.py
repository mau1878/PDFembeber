import streamlit as st
from PyPDF2 import PdfWriter, PdfReader, PdfMerger
import io
import os
import time

# --- PDF Helper Functions ---

def embed_files(main_pdf_data, files_to_embed, main_pdf_name, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Starting embed_files for {main_pdf_name}")
    try:
        pdf_writer = PdfWriter()
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
        if not pdf_files_data:
            raise ValueError("No PDFs to merge")
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
        else:  # "Merge PDFs"
            return merge_pdfs(task['ordered_pdfs'], task['main_pdf_name'], debug_logs)
    except Exception as e:
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error processing task: {str(e)}")
        raise

# --- Form Callback Function ---

def add_task():
    st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Add Task callback triggered")
    
    main_pdf = st.session_state.get('main_pdf_input')
    operation = st.session_state.get('operation_input', 'Embed files as attachments')
    additional_files = st.session_state.get('additional_files_input', [])
    ordered_pdf_names = st.session_state.get('ordered_pdf_names_input', [])

    st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Main PDF: {main_pdf.name if main_pdf else 'None'}, Operation: {operation}, Additional Files: {[f.name for f in additional_files] if additional_files else []}, Ordered PDFs: {ordered_pdf_names}")

    if not main_pdf:
        st.error("Please upload a main PDF file.")
        st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error: No main PDF uploaded")
        return
    if operation == "Merge PDFs":
        if not additional_files:
            st.error("Please upload at least one additional PDF for merging.")
            st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error: No additional PDFs for merging")
            return
        if not ordered_pdf_names:
            # Fallback to default order if multiselect fails
            pdf_names = [main_pdf.name] + [f.name for f in additional_files]
            st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] No PDFs selected, using default order: {pdf_names}")
            ordered_pdf_names = pdf_names

    try:
        main_pdf_data = io.BytesIO(main_pdf.read())
        additional_files_data = [(io.BytesIO(f.read()), f.name) for f in additional_files] if additional_files else []
        
        new_task = {
            'main_pdf_data': main_pdf_data, 'main_pdf_name': main_pdf.name,
            'operation': operation, 'additional_files': additional_files_data, 'ordered_pdfs': None
        }

        if operation == "Merge PDFs":
            all_pdfs_map = {name: data for data, name in [(main_pdf_data, main_pdf.name)] + additional_files_data}
            final_ordered_pdfs = [(all_pdfs_map[name], name) for name in ordered_pdf_names if name in all_pdfs_map]
            new_task['ordered_pdfs'] = final_ordered_pdfs
            st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merge order set: {ordered_pdf_names}")
        
        st.session_state.tasks.append(new_task)
        st.toast(f"✅ Task '{main_pdf.name}' added to queue!")
        st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Task added, total tasks: {len(st.session_state.tasks)}")
        
        # Reset form inputs after successful task addition
        st.session_state.main_pdf_input = None
        st.session_state.additional_files_input = []
        st.session_state.ordered_pdf_names_input = []
        
    except Exception as e:
        st.error(f"Failed to add task: {e}")
        st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error adding task: {e}")

# --- Main App ---

def main():
    st.title("PDF File Manager 🚀")

    if 'tasks' not in st.session_state:
        st.session_state.tasks = []
    if 'debug_logs' not in st.session_state:
        st.session_state.debug_logs = []
    if 'processed_results' not in st.session_state:
        st.session_state.processed_results = []

    st.header("1. Add New Task")

    with st.form(key="pdf_form", clear_on_submit=False):
        main_pdf = st.file_uploader("Upload Main PDF File", type=['pdf'], key="main_pdf_input")
        operation = st.radio(
            "Choose Operation:", ["Embed files as attachments", "Merge PDFs"], horizontal=True, key="operation_input"
        )
        
        additional_files = []
        if operation == "Embed files as attachments":
            additional_files = st.file_uploader(
                "Upload Files to Embed (optional)",
                type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],
                accept_multiple_files=True, key="additional_files_input"
            )
            if 'ordered_pdf_names_input' in st.session_state:
                st.session_state.ordered_pdf_names_input = []
        else:  # "Merge PDFs"
            additional_files = st.file_uploader(
                "Upload Additional PDFs to Merge (required)",
                type=['pdf'], accept_multiple_files=True, key="additional_files_input"
            )
            
            if main_pdf and additional_files:
                pdf_names = [main_pdf.name] + [f.name for f in additional_files]
                # Force initialize ordered_pdf_names_input
                if 'ordered_pdf_names_input' not in st.session_state or not st.session_state.ordered_pdf_names_input:
                    st.session_state.ordered_pdf_names_input = pdf_names
                try:
                    ordered_pdfs = st.multiselect(
                        "Arrange merge order (click to select/reorder):",
                        options=pdf_names,
                        default=st.session_state.ordered_pdf_names_input,
                        key="ordered_pdf_names_input",
                        help="Select and arrange PDFs in the desired merge order. Defaults to all uploaded PDFs."
                    )
                    st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Multiselect updated: {ordered_pdfs}")
                    st.session_state.ordered_pdf_names_input = ordered_pdfs
                except Exception as e:
                    st.error(f"Error in merge order selection: {e}")
                    st.session_state.debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error in multiselect: {e}")
                    st.session_state.ordered_pdf_names_input = pdf_names
            else:
                if 'ordered_pdf_names_input' in st.session_state:
                    st.session_state.ordered_pdf_names_input = []

        st.form_submit_button("➕ Add Task to Queue", on_click=add_task)

    if st.session_state.tasks:
        st.header("2. Process Task Queue")
        with st.expander("View Tasks", expanded=True):
            for i, task in enumerate(st.session_state.tasks):
                st.write(f"**Task {i+1}:** {task['operation']} on '{task['main_pdf_name']}'")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ Process All Tasks", use_container_width=True, type="primary"):
                with st.spinner("Processing..."):
                    new_results = []
                    for i, task in enumerate(st.session_state.tasks):
                        try:
                            output_buffer, output_filename = process_task(task, st.session_state.debug_logs)
                            output_buffer.seek(0)
                            new_results.append({'data': output_buffer.getvalue(), 'filename': output_filename})
                        except Exception as e:
                            st.error(f"Error processing task {i+1}: {e}")
                    st.session_state.processed_results.extend(new_results)
                st.success("All tasks processed!")
                st.session_state.tasks = []
                st.rerun()

        with col2:
            if st.button("❌ Clear All Tasks", use_container_width=True):
                st.session_state.tasks = []
                st.session_state.debug_logs = []
                st.session_state.main_pdf_input = None
                st.session_state.additional_files_input = []
                st.session_state.ordered_pdf_names_input = []
                st.toast("🗑️ All tasks cleared.")
                st.rerun()
        
        with col3:
            if st.button("🗑️ Clear Processed Files", use_container_width=True):
                st.session_state.processed_results = []
                st.toast("🗑️ Processed files cleared.")
                st.rerun()

    if st.session_state.processed_results:
        st.header("3. Download Processed Files")
        with st.expander("Download Files", expanded=True):
            for i, res in enumerate(st.session_state.processed_results):
                st.download_button(
                    label=f"Download '{res['filename']}'",
                    data=res['data'],
                    file_name=res['filename'],
                    mime="application/pdf",
                    key=f"download_processed_{i}"
                )
    
    st.subheader("Debug Logs")
    with st.expander("View Debug Logs", expanded=False):
        log_text = "\n".join(reversed(st.session_state.debug_logs))
        st.text_area(
            "Debug Log Output",
            value=log_text,
            height=200,
            key="debug_log_area",
            label_visibility="collapsed"
        )

if __name__ == "__main__":
    main()
