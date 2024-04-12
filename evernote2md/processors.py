from typing import List

from prefect import task

from evernote2md.link_corrector import LinkFixer, ArticleCleaner
from evernote2md.note_classifier import NoteClassifier
from evernote2md.notes_service import note_metadata, deep_notes_iterator, NoteTO
from evernote2md.utils import as_sqllite
from link_corrector import traverse_notes

@task(persist_result=True)
def clean_articles(context_dir, db, q) -> List[NoteTO]:
    indb = as_sqllite(context_dir + '/' + db)
    notes = list(deep_notes_iterator(indb, q))

    notes_cleaned = traverse_notes(notes, processor=ArticleCleaner())
    return notes_cleaned

@task
def fix_links(context_dir, notes_cleaned: List[NoteTO]) -> List[NoteTO]:
    from link_corrector import traverse_notes

    notes_p = note_metadata(context_dir, active=True)
    notes_trash = note_metadata(context_dir, active=True)
    link_fixer = LinkFixer(notes_p, notes_trash)
    # pd.DataFrame(link_fixer.buffer).to_csv(f'{context_dir}/links.csv')

    return traverse_notes(notes_cleaned, link_fixer)

@task
def enrich_data(links_fixed: List[NoteTO]) -> List[NoteTO]:
    notes_classified = traverse_notes(notes=links_fixed, processor=NoteClassifier())
    return notes_classified
