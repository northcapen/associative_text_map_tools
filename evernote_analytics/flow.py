from prefect import flow, task, serve

from prefect_shell import ShellOperation

from notes_service import read_notes, mostly_articles_notebooks
from utils import as_sqllite

OUT_DB = 'en_backup.db'
OUT_DB_CORR = 'en_backup_corr.db'

@task
def correct_links(db, context_dir):
    from link_corrector import process_incorrect_links

    inclusive_filter = lambda nb: nb.name not in mostly_articles_notebooks
    exclusive_filter = lambda nb: nb.stack in ['Core', 'Maps']


    ShellOperation(commands=[f'cd {context_dir} && cp {db} {OUT_DB_CORR}']).run()
    process_incorrect_links(as_sqllite(context_dir + '/' + OUT_DB_CORR), exclusive_filter)

@task
def export_enex(db, context_dir):
    command = f"cd {context_dir} && evernote-backup export -d {db} --overwrite export/"
    print(command)
    ShellOperation(commands=[command]).run()

@task
def yarle(context_dir, enex):
    command = f"cd {context_dir} && npx -p yarle-evernote-to-md@latest yarle yarle --configFile ../config.json"
    print(command)
    ShellOperation(commands=[command]).run()
@task
def db_to_parquet(context_dir):
    df = read_notes(as_sqllite(context_dir + '/'+ OUT_DB))
    df.to_parquet(f'{context_dir}/raw_notes')

@flow
def evernote_to_obsidian_flow(context_dir):
    correct_links(db=OUT_DB, context_dir=context_dir)
    export_enex(OUT_DB_CORR, context_dir)
    yarle(context_dir, enex=None)
    db_to_parquet(context_dir)

if __name__ == '__main__':
    full = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow', parameters={'context_dir' : 'full'}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow-small', parameters={'context_dir' : 'small'}
    )
    serve(full, small)