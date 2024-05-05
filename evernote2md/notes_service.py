from dataclasses import dataclass

import logging
from sqlite3 import Connection

from typing import Iterable, Callable, Dict, Any

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
    status: str

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
    
    def as_dict(self):
        return {
            'id' : self.note.guid,
            'title' : self.note.title, 'created': self.note.created, 'updated': self.note.updated,
            'tagNames' : self.note.tagNames,
            'active' : self.note.active,
            'contentLength' : self.note.contentLength,
            'content' : self.note.content,
            'notebook' : self.notebook.name,
            'stack' : self.notebook.stack
        }

def read_notebooks(cnx):
    def to_row(notebook):
        return {'guid': notebook.guid, 'name': notebook.name, 'stack': notebook.stack}

    df = pd.DataFrame([to_row(nb) for nb in NoteBookStorage(cnx).iter_notebooks()])
    return df



def deep_notes_iterator(cnx: Connection, condition: Callable) -> Iterable[NoteTO]:
    in_storage = NoteStorage(cnx)
    in_nb_storage = NoteBookStorage(cnx)

    for nb in list(in_nb_storage.iter_notebooks()):
        logger.debug(f'Processing {nb.name}')
        if condition(nb):
            for n in in_storage.iter_notes(nb.guid):
                yield NoteTO(n, nb, status=None)
