"""
BUILD TIME pipeline (diagram boxes 1A to 6B).

    loaders.py           1A-1D  read raw files from data/raw
    cleaners.py          2A-2C  clean markdown, resolve Slack ids, group threads
    entity_resolver.py   3      one canonical id per real-world entity
    graph_extractors.py  4A     turn records into graph nodes and edges
    graph_writer.py      4A->6A write nodes and edges to Neo4j with MERGE
    chunker.py           4B     parent-child chunking
    vector_writer.py     5B->6B embed child chunks and write them to Neo4j
    pipeline.py                 runs all of the above in order
"""
