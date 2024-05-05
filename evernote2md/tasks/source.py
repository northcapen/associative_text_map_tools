import datetime
import pickle
import sqlite3
from typing import List

import pandas as pd
from prefect import task

from evernote2md.notes_service import NoteTO, deep_notes_iterator
from evernote2md.tasks.transforms import logger

NOTES_PARQUET = 'notes.parquet'
NOTES_PICKLE = 'notes.pickle'


@task
def convert_db_to_pickle(context_dir, db, q):
    indb = _as_sqllite(context_dir + '/' + db)
    notes = list(deep_notes_iterator(indb, q))

    x = max(n.note.updated for n in notes)
    logger.info('Last known date: %s', datetime.date.fromtimestamp(x / 1000))

    with open(f'{context_dir}/notes.pickle', 'wb') as f:
        pickle.dump(notes, f)

def _as_sqllite(db_path):
    cnx = sqlite3.connect(db_path)
    cnx.row_factory = sqlite3.Row
    return cnx


@task
def write_notes_dataframe(context_dir, notes: List[NoteTO]):
    df = pd.DataFrame([note.as_dict() for note in notes])
    df.to_parquet(f'{context_dir}/{NOTES_PARQUET}')


@task
def read_pickled_notes(context_dir: str) -> List[NoteTO]:
    with open(f'{context_dir}/{NOTES_PICKLE}', 'rb') as f:
        return pickle.load(f)


@task
def read_notes_dataframe(context_dir: str) -> pd.DataFrame:
    return pd.read_parquet(f'{context_dir}/{NOTES_PARQUET}')
