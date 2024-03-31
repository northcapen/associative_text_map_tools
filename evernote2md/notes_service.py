from dataclasses import dataclass

import logging

from typing import Iterable, Callable

import lzma
import pickle
from evernote.edam.type.ttypes import Note, Notebook

from evernote_backup.note_storage import NoteStorage, NoteBookStorage

import pandas as pd
from tqdm import tqdm

from utils import iterable_to_sql_in

mostly_articles_notebooks = ['Life Mapping External', 'Articles Archive', 'IT Articles', 'Articles',
                             'ML Articles']

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('application.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

@dataclass
class NoteTO:
    note: Note
    notebook: Notebook

    @property
    def guid(self):
        return self.note.guid

    @property
    def title(self):
        return self.note.title

    @property
    def notebook_name(self):
        return self.notebook.name

    @property
    def content(self):
        return self.note.content

def read_notes(cnx):
    sql = f"""select n.guid, title, raw_note, n.name notebook, stack, notebook_guid
    from notes join notebooks n on notes.notebook_guid = n.guid
    where name not in ({iterable_to_sql_in(mostly_articles_notebooks)})
    """
    cur = cnx.execute(sql)
    result = cur.fetchall()
    #%%
    def to_note(row):
        note = pickle.loads(lzma.decompress(row["raw_note"]))

        #return note
        return { 'id' : note.guid,
            'title' : note.title, 'created': note.created, 'updated': note.updated,
            'tagNames' : note.tagNames, 'active' : note.active, 'contentLength' : note.contentLength,
            'content' : note.content,
            'notebook' : row['notebook'],
            'stack' : row['stack']
        }

    notes_df = pd.DataFrame([to_note(row) for row in tqdm(result)])

    df = notes_df.query('active').copy()
    df['created'] = pd.to_datetime(df['created'], unit='ms')
    df['updated'] = pd.to_datetime(df['updated'], unit='ms')
    #%%
    return df

def read_notebooks(cnx):
    def to_row(notebook):
        return {'guid': notebook.guid, 'name': notebook.name, 'stack': notebook.stack}

    df = pd.DataFrame([to_row(nb) for nb in NoteBookStorage(cnx).iter_notebooks()])
    return df



def deep_notes_iterator(cnx, condition: Callable) -> Iterable[NoteTO]:
    in_storage = NoteStorage(cnx)
    in_nb_storage = NoteBookStorage(cnx)

    for nb in list(in_nb_storage.iter_notebooks()):
        logger.debug(f'Processing {nb.name}')
        if condition(nb):
            for n in in_storage.iter_notes(nb.guid):
                yield NoteTO(n, nb)

def iter_notes_trash(cnx):
    return NoteStorage(cnx).iter_notes_trash()
