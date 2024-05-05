import datetime
import logging
import pickle
from typing import List

import pandas as pd
from prefect import task

from evernote2md.link_corrector import LinkFixer, ArticleCleaner
from evernote2md.note_classifier import NoteClassifier
from evernote2md.notes_service import note_metadata, deep_notes_iterator, NoteTO
from evernote2md.utils import as_sqllite
from link_corrector import traverse_notes

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@task
def db_to_pickle(context_dir, db, q):
    indb = as_sqllite(context_dir + '/' + db)
    notes = list(deep_notes_iterator(indb, q))

    x = max(n.note.updated for n in notes)
    logger.info('Last known date: %s', datetime.date.fromtimestamp(x / 1000))

    with open(f'{context_dir}/notes.pickle', 'wb') as f:
        pickle.dump(notes, f)


@task
def read_pickled_notes(context_dir):
    with open(f'{context_dir}/notes.pickle', 'rb') as f:
        return pickle.load(f)

def read_raw_notes(context_dir):
    return pd.read_parquet(f'{context_dir}/raw_notes.parquet')


@task(persist_result=True)
def clean_articles(notes) -> List[NoteTO]:
    notes_cleaned = traverse_notes(notes, processor=ArticleCleaner())
    return notes_cleaned

@task
def fix_links(context_dir, notes_cleaned: List[NoteTO]) -> List[NoteTO]:
    from link_corrector import traverse_notes

    raw_notes_all = read_raw_notes(context_dir)
    notes_p = note_metadata(raw_notes_all, active=True)
    notes_trash = note_metadata(raw_notes_all, active=True)
    link_fixer = LinkFixer(notes_p, notes_trash)
    pd.DataFrame(link_fixer.buffer).to_csv(f'{context_dir}/links.csv')

    return traverse_notes(notes_cleaned, link_fixer)

@task
def enrich_data(links_fixed: List[NoteTO]) -> List[NoteTO]:
    notes_classified = traverse_notes(notes=links_fixed, processor=NoteClassifier())
    return notes_classified
