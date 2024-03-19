import sqlite3


def iterable_to_sql_in(it):
    return ', '.join(map(lambda x: "'" + x + "'", it))

def as_sqllite(db_path):
    cnx = sqlite3.connect(db_path)
    cnx.row_factory = sqlite3.Row
    return cnx
