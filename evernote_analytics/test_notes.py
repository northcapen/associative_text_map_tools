from evernote_analytics.notes import fix_link_names


def test_fix_links():
    content = """<content>
      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note><div><a href="evernote:///view/9214951/s86/eac75a87-f509-4eb3-a53c-9718cc6437d9/eac75a87-f509-4eb3-a53c-9718cc6437d9/" style="color: #69aa35;">B</a></div></en-note>]]>
    </content>"""
    notes = {'eac75a87-f509-4eb3-a53c-9718cc6437d9' : 'B_newname'}
    x = fix_link_names(content, notes)
    assert 'B_newname' in x

