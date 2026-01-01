import sqlite3

out_db = sqlite3.connect("out.db")
out_db.row_factory = sqlite3.Row

out_db.execute("""CREATE TABLE notebooks(
                        guid TEXT PRIMARY KEY,
                        name TEXT,
                        stack TEXT
                    )""")


out_db.execute(
    """CREATE TABLE notes(
                    guid TEXT PRIMARY KEY,
                    title TEXT,
                    notebook_guid TEXT,
                    is_active BOOLEAN,
                    raw_note BLOB
                )
"""
)

out_db.execute(
    """CREATE TABLE config(
                    name TEXT PRIMARY KEY,
                    value TEXT
                )
"""
)


out_db.execute("")
