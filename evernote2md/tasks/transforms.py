import logging
from typing import Any

import pandas as pd
from evernote.edam.type.ttypes import Note
from prefect import task

from evernote2md.notes_service import NoteTO
from evernote2md.prepared.link_corrector import ArticleCleaner, LinkFixer, traverse_notes
from evernote2md.prepared.markdown_postprocessor import process_markdown_directory
from evernote2md.prepared.note_classifier import NoteClassifier

logger = logging.getLogger(__name__)


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


@task
def postprocess_multilanguage_titles(context_dir: str, md_folder: str = "md", output_dir: str | None = None) -> dict:
    """
    Post-process markdown files to handle multilanguage titles.

    - Renames files: 'Presense _ Присутствие.md' → 'Presense.md'
    - Adds aliases: aliases: ["Присутствие"]
    - Updates all wiki-links across the vault

    Args:
        context_dir: Base directory for data
        md_folder: Name of markdown folder (default: "md")
        output_dir: If specified, export processed files to this directory instead of modifying in place
    """
    md_root = f"{context_dir}/{md_folder}"
    logger.info(f"Post-processing multilanguage titles in {md_root}")

    if output_dir:
        logger.info(f"Output directory: {output_dir}")

    result = process_markdown_directory(md_root, output_dir=output_dir)

    logger.info(f"Post-processing complete: {result}")
    return result
