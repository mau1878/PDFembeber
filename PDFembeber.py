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
        raise

def process_task(task, debug_logs):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Processing task: {task['operation']} for {task['main_pdf_name']}")
    try:
        if task['operation'] == "Embed files as attachments":
            return embed_files(task['main_pdf_data'], task['additional_files'], task['main_pdf_name'], debug_logs)
        else:
            all_pdfs = [(task['main_pdf_data'], task['main_pdf_name'])] + task['additional_files']
            return merge_pdfs(all_pdfs, task['order'], task['main_pdf_name'], debug_logs)
    except Exception as e:
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error processing task: {str(e)}")
        raise

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
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] App started or reran")
    
    # Debug log display
    st.subheader("Debug Logs")
    with st.expander("View Debug Logs", expanded=True):
        for log in debug_logs:
            st.write(log)
    
    # Display pending tasks
    if st.session_state.tasks:
        st.subheader("Pending Tasks")
        for i, task in enumerate(st.session_state.tasks):
            st.write(f"Task {i+1}: {task['operation']} - Main PDF: {task['main_pdf_name']}")
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Displaying {len(st.session_state.tasks)} tasks")
    
    # Task input section
    st.subheader("Add New Task")
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Rendering form with key: pdf_form_{st.session_state.form_key}")
    
    with st.form(key=f"pdf_form_{st.session_state.form_key}"):
        main_pdf = st.file_uploader("Upload main PDF file", type=['pdf'], key=f"main_pdf_{st.session_state.form_key}")
        
        operation = st.radio(
            "Choose operation:",
            ["Embed files as attachments", "Merge PDFs"],
            key=f"operation_{st.session_state.form_key}"
        )
        debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Operation selected: {operation}")
        
        additional_files = []
        order = None
        
        if operation == "Embed files as attachments":
            additional_files = st.file_uploader(
                "Upload files to embed",
                type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],
                accept_multiple_files=True,
                key=f"embed_files_{st.session_state.form_key}"
            )
        else:
            additional_files = st.file_uploader(
                "Upload PDFs to merge",
                type=['pdf'],
                accept_multiple_files=True,
                key=f"merge_files_{st.session_state.form_key}"
            )
            
            if additional_files and main_pdf:
                all_pdfs = [main_pdf] + additional_files
                pdf_names = [main_pdf.name] + [pdf.name for pdf in additional_files]
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] PDFs for merge: {[name for name in pdf_names]}")
                
                st.write("Arrange PDF order (1 = first):")
                if st.session_state.form_key not in st.session_state.pdf_order:
                    st.session_state.pdf_order[st.session_state.form_key] = list(range(len(all_pdfs)))
                
                order = st.session_state.pdf_order[st.session_state.form_key]
                
                cols = st.columns(len(all_pdfs))
                for i, col in enumerate(cols):
                    with col:
                        new_pos = st.number_input(
                            pdf_names[i],
                            min_value=1,
                            max_value=len(all_pdfs),
                            value=order[i] + 1,
                            key=f"pdf_{st.session_state.form_key}_{i}"
                        ) - 1
                        order[i] = new_pos
                
                order = sorted(range(len(order)), key=lambda k: order[k])
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Merge order: {order}")
        
        submit = st.form_submit_button("Add Task")
        
        if submit:
            debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Add Task button clicked")
            if not main_pdf:
                st.error("Please upload a main PDF file.")
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error: No main PDF uploaded")
            elif not additional_files:
                st.error("Please upload additional files.")
                debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error: No additional files uploaded")
            else:
                try:
                    main_pdf_data = io.BytesIO(main_pdf.read())
                    additional_files_data = [(io.BytesIO(file.read()), file.name) for file in additional_files]
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Main PDF: {main_pdf.name}, Additional files: {[f[1] for f in additional_files_data]}")
                    
                    st.session_state.tasks.append({
                        'main_pdf_data': main_pdf_data,
                        'main_pdf_name': main_pdf.name,
                        'additional_files': additional_files_data,
                        'operation': operation,
                        'order': order if operation == "Merge PDFs" else None
                    })
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Task added, total tasks: {len(st.session_state.tasks)}")
                    
                    st.session_state.form_key += 1
                    st.session_state.pdf_order.pop(st.session_state.form_key - 1, None)
                    st.success("Task added successfully! Form will reset.")
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Form key incremented to {st.session_state.form_key}")
                except Exception as e:
                    st.error(f"Failed to add task: {str(e)}")
                    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] Error adding task: {str(e)}")
    
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
