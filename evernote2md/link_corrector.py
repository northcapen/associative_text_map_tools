import logging
import traceback
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict

import pandas as pd
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from notes_service import NoteTO

logger = logging.getLogger(__name__)


def traverse_notes(notes, processor):
    statuses = []
    notess = []
    for note in tqdm(notes.values()):
        with logging_redirect_tqdm():
            try:
                if note.note.contentLength >= 50000:
                    logger.info(f'Clearing note {note.note.title}')
                    note.note.content = f'Cleared note, original size was {note.note.contentLength}'
                    status = 'cleared'
                    notess.append(note.note)
                else:
                    note_transformed = processor.transform(note=note)
                    if note_transformed:
                        notess.append(note_transformed.note)
                        status = 'success'
                    else:
                        status = 'unparsed'
            except Exception as e:
                logger.error(f'Failed note {note.title} with exception {e}')
                logger.error(traceback.format_exc())
                status = 'failed'

            statuses.append({'guid' : note.guid, 'title' : note.title, 'status' : status})

    pd.DataFrame(statuses).to_csv('notes_status.csv')
    return notess

class NoteTransformer:

    def transform(self, note: NoteTO) -> Optional[NoteTO]:
        raise NotImplementedError

class LinkFixer(NoteTransformer):
    def __init__(self, notes, notes_trash):
        self.notes = notes
        self.notes_trash = notes_trash
        self.buffer = []

    def transform(self, note: NoteTO) -> Optional[NoteTO]:
        status, root = self.parse_content(note)
        if not status:
            return None
        if not root:
            return note

        logger.debug(f'Processing {note.title}')
        for a in root.findall('.//a'):
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
                a.attrib['href'] = a.text
                a.attrib['type'] = 'file'
                for child in list(a): 
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

    def parse_content(self, note) -> (bool, Optional[ET.Element]):
        try:
            root = ET.fromstring(note.content.replace('&nbsp;', ' '))

            # if root.text and root.text.strip():
            #     logger.info(f'Found text in root element {root.text}, parsing it as XML')
            #     root = ET.fromstring(root.text.strip())

        except ET.ParseError as e:
            logger.error(f'Couldnt parse note {e}"')
            logger.error(root.text)
            logger.error(list(root))
            return False, None

        return True, root


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
