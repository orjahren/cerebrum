# -*- coding: iso-8859-1 -*-
import sys
sys.stderr = sys.stdout

from TransitionMaps import TransitionMap

m = TransitionMap()
print m

def add(c, s):
  print
  print "adding", repr(c), "-->", repr(s)
  m.add_transition(c, s)
  print m
  print "keys:", m.keys()

add('a','alpha')
add('e', 'eta')
add('f', 'foo')
add('i', 'iota')
add('i', 'imp')
add('eol', 'elephant')



# arch-tag: f9718a18-0048-4490-a9d9-4114667d7c74
