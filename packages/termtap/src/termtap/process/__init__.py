"""Process tree analysis for termtap pane-centric architecture.

Internal module - external users import directly from submodules:
  - from termtap.process.tree import ProcessNode, get_process_chain
  - from termtap.process.handlers import get_handler

All high-level process detection is now handled through Pane objects.
"""
