import traceback
from datetime import datetime

from typing import Callable, Optional, Dict

import logging
from sqlite3 import Connection

# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from evernote_backup.note_storage import NoteStorage
from tqdm import tqdm

from notes_service import deep_notes_iterator, NoteTO, iter_notes_trash

from tqdm.contrib.logging import logging_redirect_tqdm


logger = logging.getLogger(__name__)


def traverse_notes(cnx_in: Connection, cnx_out: Connection, notes_query: Callable, processor):
    out_storage = NoteStorage(cnx_out)

    notes = {note.guid: note for note in (deep_notes_iterator(cnx_in, notes_query))}
    notes_trash = {note.guid : note for note in iter_notes_trash(cnx_in)}
    processor.notes = notes
    processor.notes_trash = notes_trash

    counter = 0
    for note in tqdm(notes.values()):
        with logging_redirect_tqdm():
            try:
                if note.note.contentLength >= 50000:
                    logger.info(f'Clearing note {note.note.title}')
                    note.note.content = f'Cleared note, original size was {note.note.contentLength}'
                else:
                    note = processor.transform(note=note)

            except Exception as e:
                logger.error(f'Failed note {note.title} with exception {e}')
                logger.error(traceback.format_exc())
                counter += 1
                continue

            if note:
                out_storage.add_note(note.note)
            else:
                counter += 1


    logger.info(f'Total notes: {len(notes.values())}, errors: {counter}')

class LinkFixer:
    def __init__(self):
        self.notes = None
        self.notes_trash = None
        self.buffer = []

    def transform(self, note: NoteTO) -> Optional[NoteTO]:
        root = self.parse_content(note)
        if not root:
            return None

        logger.debug(f'Processing {note.title}')
        for a in root.findall('div/a'):
            logger.debug(f'New link {a.text}')
            if a.text is None and not len(a.findall('*')):
                continue

            if not is_evernote_link(a):
                continue

            old_name = a.text
            guid_from_link = parse_a(a)
            if guid_from_link in self.notes:
                linked_note = self.notes[guid_from_link]
                a.text = linked_note.title
                for child in list(a):  # We use list() to create a copy of the children list
                    a.remove(child)
                status = 'success'
            elif self.notes_trash and guid_from_link in self.notes_trash:
                logger.error(f'Processing note {note.title}, link {a.text} found in trash')
                status = 'trash'
                linked_note = None
            else:
                logger.error(f'Processing note {note.title}, link {a.text} not found')
                status = 'fail'
                linked_note = None

            x = {
                'from_title' : note.title,
                'from_guid' : note.guid,
                'to_guid' : linked_note.guid if linked_note else None,
                'to_old' : old_name,
                'to_new' : linked_note.title if linked_note else None,
                'status' : status,
                'ts' : datetime.now()
            }
            self.buffer.append(x)

        result = str(ET.tostring(root, xml_declaration=False, encoding='unicode'))
        note.note.content = result
        return note

    def parse_content(self, note):
        try:
            root = ET.fromstring(note.content.replace('&nbsp;', ' '))

            if root.text and root.text.strip():
                logger.info(f'Found text in root element {root.text}, parsing it as XML')
                root = ET.fromstring(root.text.strip())
            #else:
            #    logger.info('Root text is empty or None')

        except ET.ParseError as e:
            logger.error(f'Couldnt parse note {e}"')
            logger.error(root.text)
            logger.error(list(root))

        return root


def is_evernote_link(a) -> bool:
    if 'href' not in a.attrib:
        return False

    return a.attrib['href'].startswith('evernote:///')

def parse_a(a) -> Optional[str]:
    href = a.attrib['href']
    if href.endswith('/'):
        href = href[:-1]

    href_components = href.split('/')

    if len(href_components) <= 2:
        logger.error(f'Invalid evernote link {href}')
        return None

    # "evernote:///view/9214951/s86/c1e7e98a-825f-4eb8-b2df-d869ed082999/c1e7e98a-825f-4eb8-b2df-d869ed082999/"
    target_note_id = href_components[-2]
    return target_note_id

def find_linked_note(a, notes: Dict[str, NoteTO]) -> Optional[NoteTO]:
    target_note_id = parse_a(a)
    if target_note_id in notes:
        # return '/'.join(['..', notes[target_note_id].notebook_name, notes[target_note_id].title])
        return notes[target_note_id]
    else:
        return None
