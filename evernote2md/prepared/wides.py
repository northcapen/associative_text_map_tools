

class NotesWide:

    def build(self, notes, notebooks_w_sensitivity, clusters):
        return (
            notes
            .merge(
                notebooks_w_sensitivity[['name', 'sensitivity']],
                left_on='notebook',
                right_on='name'
            )
            .merge(clusters, on='stack', how='left')
        )


class LinksWide:

    def build(self, notes_wide, links):
        KEY = ['notebook', 'title', 'sensitivity', 'cluster']
        return (
            links[['from_guid', 'to_guid']]
            .merge(notes_wide[['id'] + KEY], left_on='from_guid', right_on='id')
            .merge(notes_wide[['id'] + KEY], left_on='to_guid', right_on='id',
                   suffixes=['_from', '_to'])
            .drop(columns=['from_guid', 'to_guid'])
        )
