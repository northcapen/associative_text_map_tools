from dataclasses import dataclass

from datetime import datetime

from typing import Callable, Optional, List, Dict

import logging
from sqlite3 import Connection

# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from evernote_backup.note_storage import NoteStorage
from tqdm import tqdm

from notes_service import deep_notes_iterator, mostly_articles_notebooks, NoteTO

from evernote.edam.type.ttypes import Note, Notebook
from tqdm.contrib.logging import logging_redirect_tqdm


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('application.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def traverse_notes(cnx_in: Connection, cnx_out: Connection, notes_query: Callable, processor):
    out_storage = NoteStorage(cnx_out)

    it = deep_notes_iterator(cnx_in, notes_query)
    notes = {note.guid : note for note in it}
    processor.notes = notes

    counter = 0
    for note in tqdm(notes.values()):
        with logging_redirect_tqdm():
            try:
                if note.note.contentLength >= 50000:
                    note.note.content = f'Cleared note, original size was {note.note.contentLength}'
                else:
                    note = processor.transform(note=note)
            except Exception as e:
                logger.info(f'Failed note {note.title} with exception {e}')
                counter += 1

            out_storage.add_note(note.note)

    logger.info(f'Total notes: {len(notes.values())}, errors: {counter}')

class LinkFixer:
    def __init__(self):
        self.notes = None
        self.buffer = []

    def transform(self, note: NoteTO) -> NoteTO:
        root = ET.fromstring(note.content)
        if root.text and root.text.strip():
            root = ET.fromstring(root.text.strip())

        logger.info(f'Processing {note.title}')
        for a in root.findall('div/a'):
            logger.info(f'New link {a.text}')
            if a.text is None and not len(a.findall('*')):
                #logger.info(f'Empty link in note {note.title}')
                continue

            if not is_evernote_link(a):
                continue

            old_name = a.text
            new_name = canonicalize_evernote_link(a, self.notes)
            if new_name:
                a.text = new_name
                for child in list(a):  # We use list() to create a copy of the children list
                    a.remove(child)
                success = True
            else:
                logger.error(f'Processing note {note.title}, link {a.text} not found')
                success = False

            x = {'from' : note.title, 'to_old' : old_name, 'to_new' : new_name, 'success' : success, 'ts' : datetime.now()}
            self.buffer.append(x)

        result = str(ET.tostring(root, xml_declaration=False, encoding='unicode'))
        note.note.content = result
        return note

def is_evernote_link(a) -> bool:
    if 'href' not in a.attrib:
        return False

    return a.attrib['href'].startswith('evernote:///')

def canonicalize_evernote_link(a, notes: Dict[str, NoteTO]) -> Optional[str]:
    href = a.attrib['href']
    if href.endswith('/'):
        href = href[:-1]

    href_components = href.split('/')

    if len(href_components) <= 2:
        logger.error(f'Invalid evernote link {href}')
        return None

    #"evernote:///view/9214951/s86/c1e7e98a-825f-4eb8-b2df-d869ed082999/c1e7e98a-825f-4eb8-b2df-d869ed082999/"
    target_note_id = href_components[-2]
    if target_note_id in notes:
        # return '/'.join(['..', notes[target_note_id].notebook_name, notes[target_note_id].title])
        return notes[target_note_id].title
    else:
        return None
