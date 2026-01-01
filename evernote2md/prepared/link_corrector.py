import logging
import traceback

# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import pandas as pd
from evernote.edam.type.ttypes import Note
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from evernote2md.notes_service import NoteTO

logger = logging.getLogger(__name__)


class NoteTransformer:
    def transform(self, note: NoteTO) -> NoteTO | None:
        raise NotImplementedError


def traverse_notes(notes: list[NoteTO], processor: NoteTransformer) -> list[NoteTO]:
    statuses = []
    out_notes = []
    for note in tqdm(notes):
        with logging_redirect_tqdm():
            try:
                note_transformed = processor.transform(note=note)
                out_notes.append(note_transformed)
                status = note_transformed.status
            except Exception as e:
                logger.error(f"Failed note {note.title} with exception {e}")
                logger.error(traceback.format_exc())
                status = "failed"

            statuses.append({"guid": note.guid, "title": note.title, "status": status})

    logger.info(f"Finished processing notes by {type(processor)}, was {len(notes)}, out {len(out_notes)}")
    processed_ratio = 1 - pd.DataFrame(statuses)["status"].isnull().mean()
    logger.info(f"Processed ratio: {processed_ratio}")
    for note in out_notes:
        note.status = None

    return out_notes


class ArticleCleaner(NoteTransformer):
    def transform(self, note: NoteTO) -> NoteTO | None:
        if note.note.contentLength >= 50000:
            logger.info(f"Clearing note {note.note.title}")
            note.note.content = f"Cleared note, original size was {note.note.contentLength}"
            note.status = "cleared"
            return note

        return note


class NoteLinkTransformer(NoteTransformer):
    def __init__(self):
        self.buffer = []

    def transform(self, note: NoteTO) -> NoteTO | None:
        status, root = self.parse_content(note)
        if not status:
            note.status = "unparsed"
            return note
        if not root:
            return note

        logger.debug(f"Processing {note.title}")
        for a in root.findall(".//a"):
            logger.debug(f"New link {a.text}")
            if a.text is None and not len(a.findall("*")):
                continue

            if not is_evernote_link(a):
                continue

            self.buffer.append(self.transform_link(note, a))

        result = str(ET.tostring(root, xml_declaration=False, encoding="unicode"))
        note.note.content = result
        note.status = "processed" if self.buffer else None
        return note

    def transform_link(self, note, a):
        return None

    def parse_content(self, note) -> (bool, ET.Element | None):
        if note.content is None or note.content.startswith("Cleared note,"):
            return False, None

        try:
            root = ET.fromstring(note.content.replace("&nbsp;", " "))

            # if root.text and root.text.strip():
            #     logger.info(f'Found text in root element {root.text}, parsing it as XML')
            #     root = ET.fromstring(root.text.strip())

        except ET.ParseError as e:
            logger.error(f'Couldnt parse note {note.title}, got error {e}"')
            # logger.error(root.text)
            # logger.error(list(root))
            return False, None

        return True, root


class LinkFixer(NoteLinkTransformer):
    def __init__(self, note_guid_to_titles_dict: dict[Any, Note], notes_trash: dict[Any, Note]):
        super().__init__()
        self.note_guid_to_titles_dict = note_guid_to_titles_dict
        self.notes_trash = notes_trash

    def transform_link(self, note, a):
        old_name = a.text
        guid_from_link = parse_a(a)

        if guid_from_link in self.note_guid_to_titles_dict:
            linked_note = self.note_guid_to_titles_dict[guid_from_link]
            a.text = linked_note.title
            a.attrib["href"] = a.text
            a.attrib["type"] = "file"
            for child in list(a):
                a.remove(child)
            status = "success"

        elif self.notes_trash and guid_from_link in self.notes_trash:
            logger.error(f"Processing note {note.title}, link {a.text} found in trash")
            status = "trash"
            linked_note = None
        else:
            logger.error(f"Processing note {note.title}, link {a.text} not found")
            status = "fail"
            linked_note = None

        return {
            "from_title": note.title,
            "from_guid": note.guid,
            "to_guid": linked_note.guid if linked_note else None,
            "to_old": old_name,
            "to_new": linked_note.title if linked_note else None,
            "status": status,
            "ts": datetime.now(),
        }


def is_evernote_link(a) -> bool:
    if "href" not in a.attrib:
        return False

    return a.attrib["href"].startswith("evernote:///")


def parse_a(a) -> str | None:
    href = a.attrib["href"]
    if href.endswith("/"):
        href = href[:-1]

    href_components = href.split("/")

    if len(href_components) <= 2:
        logger.error(f"Invalid evernote link {href}")
        return None

    # "evernote:///view/9214951/s86/c1e7e98a-825f-4eb8-b2df-d869ed082999/c1e7e98a-825f-4eb8-b2df-d869ed082999/"
    target_note_id = href_components[-2]
    return target_note_id


def find_linked_note(a, notes: dict[str, NoteTO]) -> NoteTO | None:
    target_note_id = parse_a(a)
    if target_note_id in notes:
        # return '/'.join(['..', notes[target_note_id].notebook_name, notes[target_note_id].title])
        return notes[target_note_id]
    else:
        return None
