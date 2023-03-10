

import xml.etree.ElementTree as ET


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


def fix_link_names(note, notes):
    root = ET.fromstring(note)
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
            a.text = notes[target_note_id]

    x =  str(ET.tostring(root, xml_declaration=True, encoding='UTF-8'))
    return f"""<content>
      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
        {x}
        ]]>
    </content>
        """
