"""
Pulls real, recent CI failures from a GitHub repo's Actions history into
UNREVIEWD candidate records for later hand-labeling.

This does NOT produce ground truth. Every "label" field here is None on
purpose - the label will be diceided later.

"""

import argparse