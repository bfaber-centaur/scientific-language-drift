#!/usr/bin/env python3
"""Small denominator and region checks; no imports from mlngrams."""
from independent_function_words import metrics,boundaries

r=metrics('Of in AND 123 of.')
assert r['tokens']==5 and r['of_count']==2 and r['of_pm']==400000
assert r['alphabetic_fraction']==.8 and r['of_alpha_pm']==500000
assert metrics('We (Smith, 2024) use AI.')['tokens']==5  # citations retained
assert metrics('⟦math⟧ of the')['tokens']==3  # labels deliberately retained
t='ABSTRACT\n'+('of the sample '*20)+'\n1\nINTRODUCTION\n'+('A sentence. '*40)+'\n2. We list a contribution\n'+('More prose. '*30)+'\n2\nMETHODS\n'+('Body. '*40)+'\nREFERENCES\nReference names.'
b=boundaries(t)
assert t[b['introduction'][1]:].startswith('2\nMETHODS')
assert b['abstract'][1]<b['introduction'][0]<b['introduction'][1]<b['pre_reference'][1]
assert 'abstract' not in boundaries('No recognizable headings here.')
print('Independent denominator and conservative-boundary checks passed.')
