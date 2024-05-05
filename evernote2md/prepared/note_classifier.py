from typing import Optional

from evernote2md.prepared.link_corrector import NoteTransformer
from evernote2md.notes_service import NoteTO


class NoteClassifier(NoteTransformer):

    def transform(self, note: NoteTO) -> Optional[NoteTO]:
        if not note.note.tagNames:
            note.note.tagNames = []

        objective = note.notebook.stack == 'Techs' or 'Ztk' in note.notebook.name
        note.note.tagNames.append('objective' if objective else 'subjective')

        shortTerm = note.notebook.stack in ['Operations', 'Simple']
        note.note.tagNames.append('short-term' if shortTerm else 'long-term')

        articles = 'Articles' in note.notebook.name
        note.note.tagNames.append('authored_by_other' if articles else 'authored_by_me')

        pro = note.notebook.stack == 'Professional'
        pro_keywords = ['Segmento', 'Panda', 'Rainbow', 'Openway', 'HolyJS', 'Demand']
        pro2 = any(keyword in note.notebook.name for keyword in pro_keywords)
        note.note.tagNames.append('it-specific' if pro or pro2 else 'not-it-specific')

        more_external = 'LJ' in note.notebook.name or objective
        note.note.tagNames.append('more-external' if more_external else 'less-external')

        note.status = 'classified'
        return note
