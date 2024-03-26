from evernote_analytics.link_corrector import canonicalize_evernote_link, LinkFixer
from dataclasses import dataclass

import xml.etree.ElementTree as ET

@dataclass
class Note:
    title: str
    content :str = None

def test_fix_links():
    content = """<content>
      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
        <en-note>
            <div><a href="evernote:///view/9214951/s86/eac75a87-f509-4eb3-a53c-9718cc6437d9/eac75a87-f509-4eb3-a53c-9718cc6437d9/" style="color: #69aa35;">B</a></div>
        </en-note>
     ]]>
    </content>"""
    p = LinkFixer()
    p.notes = {'eac75a87-f509-4eb3-a53c-9718cc6437d9' : Note(title='B_newname')}
    x = p.transform(Note(title='B', content=content))
    assert '>B_newname<' in x.content

def test_evernote_link():
    x = """<a href="evernote:///view/9214951/s86/b/x/" style="color: #69aa35;">B</a>"""
    a = ET.fromstring(x)
    assert 'B_newname' in canonicalize_evernote_link(a, {'b' : Note(title='B_newname')})


def test_change_http_link():
    x = """<a href="https://www.smartsheet.com/" style="color: #69aa35;">B</a>"""
    a = ET.fromstring(x)
    assert canonicalize_evernote_link(a, {'b' : Note(title='B_newname')}) is None

def test_evernote_with_html():
    content = """<en-note><div><a href="evernote:///view/9214951/s86/b/x/" rev="en_rl_none"><span style="color:#69aa35;">B</span></a></div></en-note>"""
    p = LinkFixer()
    p.notes = {'b': Note(title='B_newname')}
    x = p.transform(Note(title='B', content=content))
    assert '>B_newname<' in x.content
