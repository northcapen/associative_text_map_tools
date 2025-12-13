import logging
from dataclasses import dataclass

import pandas as pd
from evernote.edam.type.ttypes import Note, Notebook
from evernote_backup.note_storage import NoteBookStorage

#todo rename to domain.py

mostly_articles_notebooks = ['Life Mapping External', 'Articles Archive', 'IT Articles', 'Articles',
                             'ML Articles']

logger = logging.getLogger(__name__)

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

    def as_dict(self, include_content):
        return {
            'id' : self.note.guid,
            'title' : self.note.title, 'created': self.note.created, 'updated': self.note.updated,
            'tagNames' : self.note.tagNames,
            'active' : self.note.active,
            'contentLength' : self.note.contentLength,
            'content' : self.note.content if include_content else None,
            'notebook' : self.notebook.name,
            'stack' : self.notebook.stack
        }

#todo move to source
def read_notebooks(cnx):
    def to_row(notebook):
        return {'guid': notebook.guid, 'name': notebook.name, 'stack': notebook.stack}

    df = pd.DataFrame([to_row(nb) for nb in NoteBookStorage(cnx).iter_notebooks()])
    return df
