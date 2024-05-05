import datetime
import pickle
import sqlite3
from sqlite3 import Connection
from typing import List, Callable, Iterable, Dict

import pandas as pd
from prefect import task

from evernote2md.notes_service import NoteTO
from evernote2md.tasks.transforms import logger
from evernote_backup.note_storage import NoteBookStorage, NoteStorage

DEFAULT_FORMAT = 'csv'

NOTES_PARQUET = 'notes.parquet'
NOTES_CSV = 'notes.csv'
NOTES_PICKLE = 'notes.pickle'


@task
def convert_db_to_pickle(context_dir, db, q):
    indb = _as_sqllite(context_dir + '/' + db)
    notes = list(_deep_notes_iterator(indb, q))

    x = max(n.note.updated for n in notes)
    logger.info('Last known date: %s', datetime.date.fromtimestamp(x / 1000))

    with open(f'{context_dir}/notes.pickle', 'wb') as f:
        pickle.dump(notes, f)

def _as_sqllite(db_path):
    cnx = sqlite3.connect(db_path)
    cnx.row_factory = sqlite3.Row
    return cnx

def _deep_notes_iterator(cnx: Connection, condition: Callable) -> Iterable[NoteTO]:
    in_storage = NoteStorage(cnx)
    in_nb_storage = NoteBookStorage(cnx)

    for nb in list(in_nb_storage.iter_notebooks()):
        logger.debug(f'Processing {nb.name}')
        if condition(nb):
            for n in in_storage.iter_notes(nb.guid):
                yield NoteTO(n, nb, status=None)


@task
def write_notes_dataframe(context_dir, notes: List[NoteTO], include_content=False, format=DEFAULT_FORMAT):
    df = pd.DataFrame([note.as_dict(include_content=include_content) for note in notes])
    if format == 'parquet':
        df.to_parquet(f'{context_dir}/{NOTES_PARQUET}')
    elif format == 'csv':
        df.to_csv(f'{context_dir}/{NOTES_CSV}')
    else:
        raise Exception('unsupported format: {}'.format(format))


@task
def write_links_dataframe(context_dir, links: List[Dict]):
    pd.DataFrame(links).to_csv(f'{context_dir}/links.csv')

@task
def read_pickled_notes(context_dir: str) -> List[NoteTO]:
    with open(f'{context_dir}/{NOTES_PICKLE}', 'rb') as f:
        return pickle.load(f)


@task
def read_notes_dataframe(context_dir: str, format=DEFAULT_FORMAT) -> pd.DataFrame:
    if format == 'csv':
        return pd.read_csv(f'{context_dir}/{NOTES_CSV}')
    elif format == 'parquet':
        return pd.read_parquet(f'{context_dir}/{NOTES_PARQUET}')
    else:
        raise Exception('unsupported format: {}'.format(format))

def convert_notebooks_db_to_dataframe(cnx: Connection):
    def to_row(notebook):
        return {'guid': notebook.guid, 'name': notebook.name, 'stack': notebook.stack}

    df = pd.DataFrame([to_row(nb) for nb in NoteBookStorage(cnx).iter_notebooks()])
    return df
