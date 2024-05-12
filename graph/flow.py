import os

import networkx as nx
from prefect import flow, task

from evernote2md.tasks.source import read_notes_dataframe, read_links_dataframe

@task
def build_cosma(context_dir):
    notes = read_notes_dataframe(context_dir)
    links = read_links_dataframe(context_dir)
    links.index.name = 'id'
    links = links.rename(columns={'from_guid' : 'source', 'to_guid' : 'target'}).reset_index()
    target = context_dir + '/cosma/'
    os.makedirs(target, exist_ok=True)
    notes.to_csv(target + 'notes.csv', index=False)
    links.to_csv(target + 'links.csv', index=False)


@task
def build_graph_ml(context_dir, notes, links):
    vertices = list(notes['id'])
    edges = links[['from_guid', 'to_guid']]
    edges = [(e[1], e[2]) for e in edges.itertuples()]

    G = nx.MultiDiGraph()
    G.add_nodes_from(vertices)
    G.add_edges_from(edges)

    connected_components = list(nx.connected_components(G.to_undirected()))
    G_main = connected_components[6]
    # a = sorted(list(nx.simple_cycles(G)), key=lambda s: len(s))
    # nx.write_gexf(G, 'notes.gexf')
    nx.write_graphml(G, 'notes_main.graphml')

@flow
def build_graph_stuff(context_dir):
    notes = read_notes_dataframe(context_dir)
    links = read_links_dataframe(context_dir)

    build_graph_ml(context_dir, notes, links)
    #build_cosma()