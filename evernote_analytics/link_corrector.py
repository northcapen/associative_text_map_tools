from typing import Callable

import logging
from sqlite3 import Connection

# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from evernote_backup.note_storage import NoteStorage
from tqdm import tqdm

from notes_service import deep_notes_iterator, mostly_articles_notebooks

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('application.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def process_incorrect_links(cnx_in: Connection, cnx_out: Connection, notes_query: Callable):
    out_storage = NoteStorage(cnx_out)

    it = deep_notes_iterator(cnx_in, notes_query)
    notes = {note.guid : note for note in it}

    counter = 0
    for note in tqdm(notes.values()):
        try:
            note.content = fix_link_names(note_content=note.content, notes=notes)
            out_storage.add_note(note)
        except Exception as e:
            logger.info(f'Failed note {note.title} with exception {e}')
            counter += 1

    print(f'Errors: {counter}')



def fix_link_names(note_content, notes):
    root = ET.fromstring(note_content)
    if root.text and root.text.strip():
        root = ET.fromstring(root.text.strip())

    for a in root.findall('div/a'):
        process_link(a, notes)

    result =  str(ET.tostring(root, xml_declaration=False, encoding='unicode'))
    return f"""{result}"""


def process_link(a, notes):
    href = a.attrib['href']
    href_components = href.split('/')
    if len(href_components) <= 2:
        return

    target_note_id = href_components[-2]
    if target_note_id in notes:
        a.text = notes[target_note_id].title
