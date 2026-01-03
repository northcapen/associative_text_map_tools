import hashlib
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from evernote.edam.type.ttypes import Note
from prefect import task
from prefect.filesystems import LocalFileSystem
from prefect.tasks import task_input_hash

from evernote2md.notes_service import NoteTO
from evernote2md.prepared.link_corrector import ArticleCleaner, LinkFixer, traverse_notes
from evernote2md.prepared.markdown_postprocessor import process_markdown_directory
from evernote2md.prepared.note_classifier import NoteClassifier

logger = logging.getLogger(__name__)

# Configure result storage for incremental runs
# Create and save block if it doesn't exist
_result_storage_block = LocalFileSystem(basepath="./prefect-results")
try:
    # Try to load existing block
    _result_storage_block.load("local-results")
    result_storage = "local-file-system/local-results"
except Exception:
    # Block doesn't exist, create and save it
    _result_storage_block.save("local-results", overwrite=True)
    result_storage = "local-file-system/local-results"


@task(persist_result=False)
def clean_articles(notes) -> list[NoteTO]:
    notes_cleaned = traverse_notes(notes, processor=ArticleCleaner())
    return notes_cleaned


@task
def fix_links(notes_df: pd.DataFrame, notes: list[NoteTO]) -> tuple[list[NoteTO], list[Any]]:
    from evernote2md.prepared.link_corrector import traverse_notes

    notes_p = _note_metadata(notes_df, active=True)
    notes_trash = _note_metadata(notes_df, active=True)
    link_fixer = LinkFixer(notes_p, notes_trash)

    notes_fixed_links = traverse_notes(notes, link_fixer)
    return notes_fixed_links, link_fixer.buffer


def _note_metadata(notes_df: pd.DataFrame, active=True) -> dict[Any, Note]:
    notes_parquet = notes_df.query("active == @active")
    mapping = {}
    for note in notes_parquet.itertuples():
        # noinspection PyUnresolvedReferences
        mapping[note.id] = Note(guid=note.id, title=note.title)

    return mapping


@task
def enrich_data(links_fixed: list[NoteTO]) -> list[NoteTO]:
    notes_enriched = traverse_notes(notes=links_fixed, processor=NoteClassifier())
    return notes_enriched


def _compute_directory_signature(md_path: Path) -> str:
    """
    Compute a hash signature of the directory based on file paths and modification times.
    This allows detecting if any files have changed.
    """
    if not md_path.exists():
        return ""

    # Collect file paths and modification times
    file_info = []
    for md_file in sorted(md_path.rglob("*.md")):
        try:
            mtime = md_file.stat().st_mtime
            file_info.append(f"{md_file.relative_to(md_path)}:{mtime}")
        except (OSError, ValueError):
            # Skip files that can't be accessed
            continue

    # Create hash from file info
    content = "\n".join(file_info)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _postprocess_cache_key_fn(context, parameters) -> str:
    """
    Generate cache key for postprocess_multilanguage_titles task.
    Uses task_input_hash for parameters and adds directory signature (file modification dates).
    """
    # Get standard hash from task parameters
    params_hash = task_input_hash(context, parameters) or ""

    # Compute directory signature based on file modification times
    context_dir = parameters.get("context_dir", "")
    md_folder = parameters.get("md_folder", "md")
    md_path = Path(context_dir) / md_folder
    dir_signature = _compute_directory_signature(md_path)

    # Combine parameter hash with directory signature
    if dir_signature:
        return f"{params_hash}_{dir_signature[:16]}"
    return params_hash or "no_cache"


@task(persist_result=True, result_storage=result_storage, cache_key_fn=_postprocess_cache_key_fn)
def postprocess_multilanguage_titles(context_dir: str, md_folder: str = "md", output_dir: str | None = None) -> dict:
    """
    Post-process markdown files to handle multilanguage titles.

    - Renames files: 'Presense _ Присутствие.md' → 'Presense.md'
    - Adds aliases: aliases: ["Присутствие"]
    - Updates all wiki-links across the vault

    Supports incremental runs using Prefect result storage and caching.
    Task will be skipped if input directory hasn't changed (same cache key).

    Args:
        context_dir: Base directory for data
        md_folder: Name of markdown folder (default: "md")
        output_dir: If specified, export processed files to this directory instead of modifying in place
    """
    md_root = f"{context_dir}/{md_folder}"
    logger.info(f"Post-processing multilanguage titles in {md_root}")

    if output_dir:
        logger.info(f"Output directory: {output_dir}")

    # Process the directory
    result = process_markdown_directory(md_root, output_dir=output_dir)

    logger.info(f"Post-processing complete: {result}")
    return result
