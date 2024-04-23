import logging

from evernote2md.flow import evernote_to_obsidian_flow

logging.getLogger('evernote_backup').setLevel(logging.DEBUG)

evernote_to_obsidian_flow(context_dir='data/small')
