import logging
import uuid

from evernote2md.link_corrector import find_linked_note, LinkFixer
from dataclasses import dataclass

import xml.etree.ElementTree as ET

from evernote2md.notes_service import NoteTO

# Create a logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add the formatter to the console handler
console_handler.setFormatter(formatter)

# Add the console handler to the logger
logger.addHandler(console_handler)


@dataclass
class Note:
    guid: str
    title: str
    content: str = None
    notebook_name: str = 'A'


def build_noteto(title, content=None):
    return NoteTO(note=Note(title=title, content=content, guid=str(uuid.uuid4())),
                  notebook=None, status='success')


def test_fix_links():
    en_note = """
        <en-note><div><a href="evernote:///view/9214951/s86/eac75a87-f509-4eb3-a53c-9718cc6437d9/eac75a87-f509-4eb3-a53c-9718cc6437d9/" style="color: #69aa35;">B</a></div></en-note>
    """
    content = en_note
    p = LinkFixer(
        note_guid_to_titles_dict={
            'eac75a87-f509-4eb3-a53c-9718cc6437d9': build_noteto(title='B_newname').note},
        notes_trash=None
    )

    x = p.transform(build_noteto(title='B', content=content))
    assert isinstance(x, NoteTO)
    assert '>B_newname<' in x.content


def wrap_in_cdata(en_note):
    return f"""<content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?><!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">{en_note}]]></content>"""


def test_evernote_link():
    x = """<a href="evernote:///view/9214951/s86/b/x/" style="color: #69aa35;">B</a>"""
    a = ET.fromstring(x)
    assert 'B_newname' in find_linked_note(a, {'b': build_noteto(title='B_newname')}).title


def test_change_http_link():
    x = """<a href="https://www.smartsheet.com/" style="color: #69aa35;">B</a>"""
    a = ET.fromstring(x)
    assert find_linked_note(a, {'b': build_noteto(title='B_newname')}) is None


def test_evernote_with_html():
    content = """<en-note><div><a href="evernote:///view/9214951/s86/b/x/" rev="en_rl_none"><span style="color:#69aa35;">B</span></a></div></en-note>"""
    p = LinkFixer(note_guid_to_titles_dict={'b': build_noteto(title='B_newname')}, notes_trash={})
    x = p.transform(build_noteto(title='B', content=content))
    assert '>B_newname<' in x.content


def test_evernote_with_embeded():
    content = """<en-note>
                    <div>
                        <a href="evernote:///view/9214951/s86/b/x/" rev="en_rl_none">
                            <span style="color:#69aa35;">B</span>
                        </a>
                    </div>
                    <ol>
                        <li>
                            <a href="evernote:///view/9214951/s86/b/x/" rev="en_rl_none">
                                <span style="color:#69aa35;">X</span>
                            </a>
                        </li>
                    </ol>
                </en-note>"""
    p = LinkFixer(
        note_guid_to_titles_dict={'b': build_noteto(title='B_newname').note},
        notes_trash={}
    )

    x = p.transform(build_noteto(title='B', content=content))
    assert len(p.buffer) == 2
    assert '>B_newname<' in x.content


def xtest_evernote_wrapped_in_cdata():
    content = wrap_in_cdata(
        """<en-note>top level text
        <div><a href="evernote:///view/9214951/s86/b/x/" rev="en_rl_none"><span style="color:#69aa35;">B</span></a></div></en-note>""")
    p = LinkFixer()
    p.note_guid_to_titles_dict = {'b': build_noteto(title='B_newname')}
    x = p.transform(build_noteto(title='B', content=content))
    assert '>B_newname<' in x.content