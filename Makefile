
.PHONY: sync publish
sync:
	pushd ~/Documents/Life\ mapping && evernote-backup sync && popd
	cp ~/Documents/Life\ mapping/en_backup.db data/full/

main_flow_small:
	PYTHONPATH=. .venv/bin/python evernote2md/runner.py small db_to_pickle

main_flow_full:
	PYTHONPATH=. .venv/bin/python evernote2md/runner.py full


publish_ga_docs:
	mkdir -p ~/IdeaProjects/GADocs/demand_wiki/
	cp -R data/demand_ztk/md ~/IdeaProjects/GADocs/demand_wiki/