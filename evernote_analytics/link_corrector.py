from sqlite3 import Connection

# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from evernote_backup.note_storage import NoteStorage

from notes_service import deep_notes_iterator


def process_incorrect_links(cnx: Connection):
    out_storage = NoteStorage(cnx)

    notes = {note.guid : note for note in deep_notes_iterator(cnx)}

    counter = 0
    for note in notes.values():
        try:
            note.content = fix_link_names(note_content=note.content, notes=notes)
            out_storage.add_note(note)
        except Exception as e:
            print(note.title, e)
            counter += 1

    print(f'Errors: {counter}')


def links(content):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content.replace('en-note', 'html').replace('\xa0', ''), "html.parser")
    for div in soup.find_all('div'):
        names = [c.name for c in div.children]
        if 'a' in names:
            texts = [c.text for c in div.children]
            for a in [c for c in div.children if c.name == 'a']:
                components = a.attrs['href'].split('/')
                yield texts[0], [c for c in components if len(c) > 0][-1]


def fix_link_names(note_content, notes):
    root = ET.fromstring(note_content)
    if root.text and root.text.strip():
        root = ET.fromstring(root.text.strip())

    for a in root.findall('div/a'):
        href = a.attrib['href']
        href_components = href.split('/')
        if len(href_components) <= 2:
            print(href)
            continue

        target_note_id = href_components[-2]

        if target_note_id in notes:
            a.text = notes[target_note_id].title

    x =  str(ET.tostring(root, xml_declaration=True, encoding='UTF-8'))
    return f"""<content>
      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
        {x}
        ]]>
    </content>
        """
