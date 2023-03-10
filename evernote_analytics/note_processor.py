import lzma
import pickle
import sys

from tqdm import tqdm

from evernote_analytics.notes import fix_link_names
from evernote_backup.note_storage import NoteStorage, NoteBookStorage


def iterable_to_sql_in(it):
    return ', '.join(map(lambda x: "'" + x + "'", it))


sys.path.append('')

import sqlite3
import pandas as pd

# Create your connection.
cnx = sqlite3.connect('/Users/antonvoskobovich/Documents/Life mapping/en_backup.db')
cnx.row_factory = sqlite3.Row

out_db = sqlite3.connect('/Users/antonvoskobovich/Documents/Life mapping/out.db')
out_db.row_factory = sqlite3.Row

mostly_articles_notebooks = ['Life Mapping External', 'Articles Archive', 'IT Articles', 'Articles', 'ML Articles']


def notebooks():
    def to_row(notebook):
        return {'guid': notebook.guid, 'name': notebook.name, 'stack': notebook.stack}

    NoteBookStorage(cnx).iter_notebooks()
    df = pd.DataFrame([to_row(nb) for nb in NoteBookStorage(cnx).iter_notebooks()])
    df.to_csv('notebooks.csv')


def db_processor():
    # notes = cnx.execute("select * from notes").fetchall()
    # black_list_notes = generate_black_list_notes()
    # notes_filtered = [row for row in notes if row['guid'] not in black_list_notes][0:100]

    notes = NoteStorage(cnx).iter_notes("8644f8b3-8565-43a3-95d8-f6fd7d9f8f21")
    out_db.execute(
        """CREATE TABLE notes(
                        guid TEXT PRIMARY KEY,
                        title TEXT,
                        notebook_guid TEXT,
                        is_active BOOLEAN,
                        raw_note BLOB
                    )
    """)

    for n in tqdm(notes):
        try:
            n.content = fix_link_names(n.content, {})
            NoteStorage(out_db).add_note(n)
        except Exception as e:
            print(n.title)
            print(e)



    #[fix_link_names(n.content, {}) for n in notes]

    # notes_df = pd.DataFrame([to_note_dict(row) for row in tqdm(notes_filtered)])
    # df = notes_df.query('active').copy()
    # df['created'] = pd.to_datetime(df['created'], unit='ms')
    # df['updated'] = pd.to_datetime(df['updated'], unit='ms')



def generate_black_list_notes():
    black_list_sql = f"""
    select notes.guid
    from notes join notebooks n on notes.notebook_guid = n.guid
    where name in ({iterable_to_sql_in(mostly_articles_notebooks)}) 
    """
    black_list_notes = set([row['guid'] for row in cnx.execute(black_list_sql).fetchall()])
    return black_list_notes


if __name__ == '__main__':
    db_processor()
    #notebooks()
