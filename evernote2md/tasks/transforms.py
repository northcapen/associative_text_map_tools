import logging
from typing import List, Dict, Any

import pandas as pd
from evernote.edam.type.ttypes import Note
from prefect import task

from evernote2md.prepared.link_corrector import LinkFixer, ArticleCleaner
from evernote2md.prepared.note_classifier import NoteClassifier
from evernote2md.notes_service import NoteTO
from evernote2md.prepared.link_corrector import traverse_notes

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@task(persist_result=True)
def clean_articles(notes) -> List[NoteTO]:
    notes_cleaned = traverse_notes(notes, processor=ArticleCleaner())
    return notes_cleaned


@task
def fix_links(context_dir: str, notes_df: pd.DataFrame, notes: List[NoteTO]) -> List[NoteTO]:
    from evernote2md.prepared.link_corrector import traverse_notes

    notes_p = _note_metadata(notes_df, active=True)
    notes_trash = _note_metadata(notes_df, active=True)
    link_fixer = LinkFixer(notes_p, notes_trash)
    pd.DataFrame(link_fixer.buffer).to_csv(f'{context_dir}/links.csv')

    return traverse_notes(notes, link_fixer)

def _note_metadata(notes_df: pd.DataFrame, active=True) -> Dict[Any, Note]:
    notes_parquet = notes_df.query('active == @active')
    mapping = {}
    for note in notes_parquet.itertuples():
         # noinspection PyUnresolvedReferences
         mapping[note.id] = Note(guid=note.id, title=note.title)

    return mapping


@task
def enrich_data(links_fixed: List[NoteTO]) -> List[NoteTO]:
    notes_enriched = traverse_notes(notes=links_fixed, processor=NoteClassifier())
    return notes_enriched
