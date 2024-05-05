import logging
import sys

from evernote2md.flow import evernote_to_obsidian_flow

logging.getLogger('evernote_backup').setLevel(logging.DEBUG)

ci_dir = sys.argv[1] if len(sys.argv) > 1 else 'small'

evernote_to_obsidian_flow(context_dir='data/' + ci_dir)
