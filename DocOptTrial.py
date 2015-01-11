"""Usage: DocOptTrial.py [--p=VALUE ...]
"""

import docopt

arguments = docopt.docopt(__doc__)
# When testing is done, this is where
# test arguments are inserted.

print "-----------------------------------"
print "Inputs:"
args = arguments.keys()
args.sort()
for arg in args:
    print "%-25s %s" % (arg, arguments[arg])
print "-----------------------------------"