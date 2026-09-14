import streamlit as st
from pypdf import PdfWriter, PdfReader
import io
import os
import re
import time
import zipfile
from collections import deque

# --- Config ---
# Streamlit Community Cloud gives ~1 CPU / ~1GB RAM per app, so we deliberately
# avoid multiprocessing (pickling overhead + resource contention isn't worth it
# at this scale) and instead focus on keeping peak memory low: raw bytes are
# stored instead of BytesIO wrappers, and each task's source bytes are dropped
# from session_state the moment it's processed.
MAX_DEBUG_LOGS = 500
TOTAL_UPLOAD_WARNING_BYTES = 150 * 1024 * 1024  # warn past 150MB in one queue


# --- Logging ---
def log(debug_logs, msg):
    debug_logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")


# --- PDF Helper Functions ---
def embed_files(main_pdf_bytes, files_to_embed, main_pdf_name, debug_logs):
    """files_to_embed: list of (bytes, filename) to attach to main_pdf_bytes.

    Uses pypdf's incremental-write mode: the original file's bytes are kept
    untouched and the attachment is appended as new content after them,
    instead of rebuilding the whole PDF object structure. This is what lets
    a pre-existing digital signature on main_pdf_bytes keep validating
    cryptographically (its /ByteRange still points at unchanged bytes).
    Falls back to a full rewrite if incremental mode can't parse the file.
    """
    log(debug_logs, f"Starting embed_files for {main_pdf_name}")
    try:
        pdf_writer = PdfWriter(fileobj=io.BytesIO(main_pdf_bytes), incremental=True)
        log(debug_logs, f"Loaded {len(pdf_writer.pages)} pages in incremental mode")
    except Exception as e:
        log(debug_logs, f"Incremental mode failed ({e}); falling back to full rewrite "
                         f"(any existing digital signature on this file WILL be invalidated)")
        pdf_writer = PdfWriter()
        pdf_reader = PdfReader(io.BytesIO(main_pdf_bytes))
        pdf_writer.append(pdf_reader)

    try:
        for file_bytes, file_name in files_to_embed:
            log(debug_logs, f"Embedding file: {file_name}")
            pdf_writer.add_attachment(file_name, file_bytes)

        base_name = os.path.splitext(main_pdf_name)[0]
        output_filename = f"{base_name}_EMBEDDED.pdf"
        output_buffer = io.BytesIO()
        pdf_writer.write(output_buffer)
        log(debug_logs, f"Embedded files, output file: {output_filename}")
        return output_buffer.getvalue(), output_filename
    except Exception as e:
        log(debug_logs, f"Error in embed_files: {str(e)}")
        raise


def merge_pdfs(pdf_files_data, main_pdf_name, debug_logs):
    """pdf_files_data: ordered list of (bytes, filename) to merge together."""
    log(debug_logs, f"Starting merge_pdfs for {main_pdf_name}")
    try:
        if not pdf_files_data:
            raise ValueError("No PDFs to merge")

        writer = PdfWriter()
        for pdf_bytes, pdf_name in pdf_files_data:
            log(debug_logs, f"Merging file: {pdf_name}")
            reader = PdfReader(io.BytesIO(pdf_bytes))
            # outline_item adds a bookmark named after the source file, so the
            # merged PDF stays navigable instead of becoming one flat page list.
            writer.append(reader, outline_item=os.path.splitext(pdf_name)[0])

        base_name = os.path.splitext(main_pdf_name)[0]
        output_filename = f"{base_name}_MERGED.pdf"
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        log(debug_logs, f"Merged PDFs, output file: {output_filename}")
        return output_buffer.getvalue(), output_filename
    except Exception as e:
        log(debug_logs, f"Error in merge_pdfs: {str(e)}")
        raise


def process_task(task, debug_logs):
    log(debug_logs, f"Processing task: {task['operation']} for {task['main_pdf_name']}")
    if task['operation'] == "Embed files as attachments":
        return embed_files(task['main_pdf_data'], task['additional_files'], task['main_pdf_name'], debug_logs)
    else:  # "Merge PDFs"
        return merge_pdfs(task['ordered_pdfs'], task['main_pdf_name'], debug_logs)


def pdf_stem(filename):
    return os.path.splitext(filename)[0]


def order_key(secondary_name, main_name, separator):
    """Sort key for a secondary matched to main_name: the leading number
    right after '<main_stem><separator>' controls order (e.g. the '2' in
    'INV-001_2_signed.pdf'). Secondaries with no such number sort after
    the numbered ones, keeping their relative upload order as a tiebreak
    (this function only supplies the numeric part of the key; the caller
    does a stable sort so upload order survives for ties)."""
    remainder = pdf_stem(secondary_name)
    prefix = pdf_stem(main_name) + separator
    if remainder.startswith(prefix):
        remainder = remainder[len(prefix):]
    else:
        remainder = ''  # exact-name match, no suffix at all
    m = re.match(r'^(\d+)', remainder)
    return (0, int(m.group(1))) if m else (1, 0)


def auto_match_secondaries(main_names, secondary_names, separator):
    """Pairs secondary files to main files by filename.

    A secondary matches a main if its stem equals the main's stem exactly,
    or starts with '<main_stem><separator>'. Requiring the separator right
    after the main's stem (rather than a plain substring/prefix test) is
    what keeps e.g. 'INV-10_x' from ever matching main 'INV-1': the
    character right after 'INV-1' in 'INV-10_x' is '0', not the separator.

    Within one main's matches, secondaries are ordered by a leading number
    right after the separator (e.g. 'INV-001_1_original.pdf' before
    'INV-001_2_signed.pdf'); secondaries with no such number keep their
    upload order and sort after the numbered ones.

    Returns (matches, ambiguous):
      matches: dict main_name -> list of auto-matched secondary_names
      ambiguous: secondary_names that matched more than one main (left
                 unassigned everywhere so the user resolves them by hand)
    """
    matches = {m: [] for m in main_names}
    ambiguous = []
    for s in secondary_names:
        s_stem = pdf_stem(s)
        candidates = [
            m for m in main_names
            if s_stem == pdf_stem(m) or s_stem.startswith(pdf_stem(m) + separator)
        ]
        if len(candidates) == 1:
            matches[candidates[0]].append(s)
        elif len(candidates) > 1:
            ambiguous.append(s)

    for m in main_names:
        matches[m] = sorted(matches[m], key=lambda s: order_key(s, m, separator))

    return matches, ambiguous


def unique_filename(existing_names, filename):
    """Avoid collisions when two tasks produce the same output filename."""
    if filename not in existing_names:
        return filename
    base, ext = os.path.splitext(filename)
    i = 2
    while f"{base} ({i}){ext}" in existing_names:
        i += 1
    return f"{base} ({i}){ext}"


def make_zip(results):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        used_names = set()
        for res in results:
            name = unique_filename(used_names, res['filename'])
            used_names.add(name)
            zf.writestr(name, res['data'])
    buf.seek(0)
    return buf.getvalue()


# --- Session State Helpers ---
def reset_form_state():
    for key in ('main_pdf_input', 'additional_files_input', 'ordered_pdf_names_input', 'default_ordered_pdfs'):
        st.session_state.pop(key, None)


def init_state():
    st.session_state.setdefault('tasks', [])
    st.session_state.setdefault('debug_logs', deque(maxlen=MAX_DEBUG_LOGS))
    st.session_state.setdefault('processed_results', [])
    st.session_state.setdefault('default_ordered_pdfs', [])


# --- Form Callback: single-task mode ---
def add_task():
    debug_logs = st.session_state.debug_logs
    log(debug_logs, "Add Task callback triggered")

    main_pdf = st.session_state.get('main_pdf_input')
    operation = st.session_state.get('operation_input', 'Embed files as attachments')
    additional_files = st.session_state.get('additional_files_input', [])
    ordered_pdf_names = st.session_state.get('ordered_pdf_names_input', [])

    if not main_pdf:
        st.error("Please upload a main PDF file.")
        log(debug_logs, "Error: No main PDF uploaded")
        return

    if operation == "Merge PDFs" and not additional_files:
        st.error("Please upload at least one additional PDF for merging.")
        log(debug_logs, "Error: No additional PDFs for merging")
        return

    if operation == "Merge PDFs" and not ordered_pdf_names:
        ordered_pdf_names = [main_pdf.name] + [f.name for f in additional_files]
        log(debug_logs, f"No order selected, using default order: {ordered_pdf_names}")

    try:
        main_pdf_bytes = main_pdf.read()
        additional_files_data = [(f.read(), f.name) for f in additional_files] if additional_files else []

        new_task = {
            'main_pdf_data': main_pdf_bytes, 'main_pdf_name': main_pdf.name,
            'operation': operation, 'additional_files': additional_files_data, 'ordered_pdfs': None
        }

        if operation == "Merge PDFs":
            all_pdfs_map = {name: data for data, name in [(main_pdf_bytes, main_pdf.name)] + additional_files_data}
            new_task['ordered_pdfs'] = [(all_pdfs_map[name], name) for name in ordered_pdf_names if name in all_pdfs_map]
            log(debug_logs, f"Merge order set: {ordered_pdf_names}")

        st.session_state.tasks.append(new_task)
        st.toast(f"✅ Task '{main_pdf.name}' added to queue!")
        log(debug_logs, f"Task added, total tasks: {len(st.session_state.tasks)}")
        reset_form_state()
    except Exception as e:
        st.error(f"Failed to add task: {e}")
        log(debug_logs, f"Error adding task: {e}")


# --- Callback: batch mode (main PDFs paired 1:N with secondary files by filename) ---
def add_matched_batch_tasks():
    debug_logs = st.session_state.debug_logs
    log(debug_logs, "Add Matched Batch Tasks callback triggered")

    main_pdfs = st.session_state.get('batch_main_pdfs_input', [])
    secondary_files = st.session_state.get('batch_secondary_files_input', [])
    operation = st.session_state.get('batch_operation_input', 'Embed files as attachments')

    if not main_pdfs:
        st.error("Please upload at least one main PDF.")
        log(debug_logs, "Error: No main PDFs uploaded for batch")
        return

    secondary_by_name = {f.name: f for f in secondary_files}
    added, skipped = 0, 0
    try:
        for main_pdf in main_pdfs:
            selected_names = st.session_state.get(f"batch_match_{main_pdf.name}", [])
            if not selected_names:
                skipped += 1
                log(debug_logs, f"Skipped '{main_pdf.name}': no matched files selected")
                continue

            main_bytes = main_pdf.getvalue()
            secondary_data = [(secondary_by_name[n].getvalue(), n) for n in selected_names if n in secondary_by_name]

            new_task = {
                'main_pdf_data': main_bytes, 'main_pdf_name': main_pdf.name,
                'operation': operation, 'additional_files': secondary_data, 'ordered_pdfs': None
            }
            if operation == "Merge PDFs":
                new_task['ordered_pdfs'] = [(main_bytes, main_pdf.name)] + secondary_data
            st.session_state.tasks.append(new_task)
            added += 1

        suffix = f" ({skipped} main PDF(s) skipped — no match selected)" if skipped else ""
        st.toast(f"✅ {added} tasks added to queue!{suffix}")
        log(debug_logs, f"Matched batch add: {added} added, {skipped} skipped, total tasks: {len(st.session_state.tasks)}")

        for key in list(st.session_state.keys()):
            if key.startswith('batch_match_'):
                del st.session_state[key]
        for key in ('batch_main_pdfs_input', 'batch_secondary_files_input', 'batch_fingerprint',
                    'batch_auto_matches', 'batch_ambiguous'):
            st.session_state.pop(key, None)
    except Exception as e:
        st.error(f"Failed to add batch tasks: {e}")
        log(debug_logs, f"Error adding matched batch tasks: {e}")


# --- Main App ---
def main():
    st.set_page_config(page_title="PDF File Manager", page_icon="🚀")
    st.title("PDF File Manager 🚀")
    init_state()
    debug_logs = st.session_state.debug_logs

    batch_mode = st.toggle(
        "Batch mode (pair many main PDFs with matching files by filename)",
        key="batch_mode_toggle",
        help="Off: build one task at a time with full control over merge order. "
             "On: upload a group of main PDFs and a group of secondary files; "
             "they're paired automatically by filename (e.g. 'INV-001.pdf' with "
             "'INV-001_signed.pdf'), with a preview you can adjust before queuing."
    )

    st.header("1. Add New Task" if not batch_mode else "1. Add Batch Tasks")

    if not batch_mode:
        with st.form(key="pdf_form", clear_on_submit=False):
            main_pdf = st.file_uploader("Upload Main PDF File", type=['pdf'], key="main_pdf_input")
            operation = st.radio(
                "Choose Operation:", ["Embed files as attachments", "Merge PDFs"], horizontal=True, key="operation_input"
            )
            if operation == "Embed files as attachments":
                st.caption("ℹ️ If the main PDF is digitally signed, embedding tries to preserve that "
                           "signature by appending changes instead of rewriting the file. This isn't "
                           "guaranteed for every PDF — verify the signature afterward before relying on it.")
            else:
                st.caption("⚠️ Merging always invalidates the digital signature of every PDF being merged "
                           "(the same is true in Adobe Acrobat's own 'Combine Files'). Re-sign after merging "
                           "if you need a valid signature on the result.")

            additional_files = []
            if operation == "Embed files as attachments":
                additional_files = st.file_uploader(
                    "Upload Files to Embed (optional)",
                    type=['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx'],
                    accept_multiple_files=True, key="additional_files_input"
                )
            else:  # "Merge PDFs"
                additional_files = st.file_uploader(
                    "Upload Additional PDFs to Merge (required)",
                    type=['pdf'], accept_multiple_files=True, key="additional_files_input"
                )
                if main_pdf and additional_files:
                    pdf_names = [main_pdf.name] + [f.name for f in additional_files]
                    st.session_state.default_ordered_pdfs = pdf_names
                    ordered_pdfs = st.multiselect(
                        "Arrange merge order (click to select/reorder):",
                        options=pdf_names,
                        default=st.session_state.default_ordered_pdfs,
                        key="ordered_pdf_names_input",
                        help="Select and arrange PDFs in the desired merge order. Defaults to all uploaded PDFs."
                    )
                else:
                    st.session_state.default_ordered_pdfs = []

            st.form_submit_button("➕ Add Task to Queue", on_click=add_task)
    else:
        # Not wrapped in st.form: the matching preview below needs to react
        # live as files are uploaded, before any "submit" click.
        st.caption("Upload your main PDFs and the files to pair with them — matches are made "
                   "automatically by filename, and you can adjust any pairing before queuing tasks.")
        separator = st.text_input(
            "Separator between a main PDF's name and a secondary file's suffix",
            value="_", max_chars=5, key="batch_separator_input",
            help="With separator '_', main 'INV-001.pdf' matches secondaries 'INV-001_signed.pdf', "
                 "'INV-001_annex.pdf', etc. Exact-name matches (no suffix) always work too.\n\n"
                 "To control the order they get attached/merged in, put a number right after the "
                 "separator: 'INV-001_1_original.pdf' before 'INV-001_2_signed.pdf'. Secondaries "
                 "without a number keep upload order and are placed after the numbered ones."
        )

        col_a, col_b = st.columns(2)
        with col_a:
            main_pdfs = st.file_uploader(
                "Main PDFs", type=['pdf'], accept_multiple_files=True, key="batch_main_pdfs_input"
            )
        with col_b:
            operation = st.radio(
                "Operation (applied to each matched pair):",
                ["Embed files as attachments", "Merge PDFs"], key="batch_operation_input"
            )
            secondary_types = ['pdf'] if operation == "Merge PDFs" else ['pdf', 'docx', 'txt', 'jpg', 'png', 'xlsx']
            secondary_files = st.file_uploader(
                "Files to pair with them", type=secondary_types,
                accept_multiple_files=True, key="batch_secondary_files_input"
            )

        if operation == "Embed files as attachments":
            st.caption("ℹ️ Embedding tries to preserve an existing digital signature on each main PDF "
                       "by appending rather than rewriting — not guaranteed for every file.")
        else:
            st.caption("⚠️ Merging invalidates the digital signature of every PDF involved (same as "
                       "Adobe Acrobat's 'Combine Files'). Re-sign after merging if you need one.")

        if main_pdfs and secondary_files:
            main_names = [f.name for f in main_pdfs]
            secondary_names = [f.name for f in secondary_files]

            stem_owner = {}
            dup_stems = set()
            for n in main_names:
                s = pdf_stem(n)
                if s in stem_owner:
                    dup_stems.add(s)
                stem_owner[s] = n
            if dup_stems:
                st.error(f"Several main PDFs share the same base name ({', '.join(dup_stems)}) — "
                        "rename them so each has a unique identifier before pairing.")

            fingerprint = (tuple(main_names), tuple(secondary_names), separator)
            if st.session_state.get('batch_fingerprint') != fingerprint:
                for key in list(st.session_state.keys()):
                    if key.startswith('batch_match_'):
                        del st.session_state[key]
                st.session_state['batch_fingerprint'] = fingerprint
                auto_matches, ambiguous = auto_match_secondaries(main_names, secondary_names, separator)
                st.session_state['batch_auto_matches'] = auto_matches
                st.session_state['batch_ambiguous'] = ambiguous

            auto_matches = st.session_state.get('batch_auto_matches', {})
            ambiguous = st.session_state.get('batch_ambiguous', [])

            st.write(f"**Matching preview** ({len(main_names)} main, {len(secondary_names)} secondary) "
                    "— adjust any row, then queue:")
            for main_name in main_names:
                st.multiselect(
                    main_name, options=secondary_names,
                    default=auto_matches.get(main_name, []),
                    key=f"batch_match_{main_name}"
                )

            assigned = set()
            for main_name in main_names:
                assigned.update(st.session_state.get(f"batch_match_{main_name}", []))
            unmatched_secondaries = [n for n in secondary_names if n not in assigned]
            unmatched_mains = [n for n in main_names if not st.session_state.get(f"batch_match_{n}", [])]

            if ambiguous:
                st.warning(f"Matched more than one main PDF — resolve manually above: {', '.join(ambiguous)}")
            if unmatched_secondaries:
                st.warning(f"Not assigned to any main PDF: {', '.join(unmatched_secondaries)}")
            if unmatched_mains:
                st.info(f"No matched files (will be skipped when queuing): {', '.join(unmatched_mains)}")

            st.button("➕ Queue Matched Tasks", on_click=add_matched_batch_tasks, disabled=bool(dup_stems))
        elif main_pdfs or secondary_files:
            st.caption("Upload both groups of files to see the matching preview.")

    if st.session_state.tasks:
        total_bytes = sum(
            len(t['main_pdf_data']) + sum(len(d) for d, _ in t['additional_files'])
            for t in st.session_state.tasks
        )
        if total_bytes > TOTAL_UPLOAD_WARNING_BYTES:
            st.warning(
                f"The queue is holding ~{total_bytes / (1024*1024):.0f}MB in memory. "
                "Streamlit Community Cloud apps run with limited RAM — consider processing "
                "in smaller batches if you hit a crash or restart."
            )

        st.header("2. Process Task Queue")
        with st.expander("View Tasks", expanded=True):
            for i, task in enumerate(st.session_state.tasks):
                st.write(f"**Task {i+1}:** {task['operation']} on '{task['main_pdf_name']}'")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Process All Tasks", use_container_width=True, type="primary"):
                    tasks = st.session_state.tasks
                    total = len(tasks)
                    progress = st.progress(0.0)
                    status = st.empty()
                    new_results = []
                    errors = 0
                    for i, task in enumerate(tasks):
                        status.text(f"Processing {i+1}/{total}: {task['main_pdf_name']} ({task['operation']})")
                        try:
                            data, filename = process_task(task, debug_logs)
                            new_results.append({'data': data, 'filename': filename})
                        except Exception as e:
                            errors += 1
                            st.error(f"Error processing task {i+1} ('{task['main_pdf_name']}'): {e}")
                        # Drop this task's source bytes now that we're done with it,
                        # instead of waiting until the whole batch finishes.
                        tasks[i] = None
                        progress.progress((i + 1) / total)
                    status.text(f"Done: {total - errors}/{total} tasks succeeded.")
                    st.session_state.processed_results.extend(new_results)
                    if errors == 0:
                        st.success("All tasks processed!")
                    st.session_state.tasks = []
                    reset_form_state()
                    st.rerun()

            with col2:
                if st.button("❌ Clear All Tasks", use_container_width=True):
                    st.session_state.tasks = []
                    st.session_state.debug_logs = deque(maxlen=MAX_DEBUG_LOGS)
                    reset_form_state()
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
            if len(st.session_state.processed_results) > 1:
                zip_bytes = make_zip(st.session_state.processed_results)
                st.download_button(
                    label=f"⬇️ Download all {len(st.session_state.processed_results)} files as .zip",
                    data=zip_bytes, file_name="pdfembeber_results.zip", mime="application/zip",
                    key="download_all_zip", type="primary"
                )
                st.divider()
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
            log_text = "\n".join(reversed(debug_logs))
            st.text_area(
                "Debug Log Output",
                value=log_text,
                height=200,
                key="debug_log_area",
                label_visibility="collapsed"
            )


if __name__ == "__main__":
    main()
