import sys

import make_stats
import read_stats

if __name__ == "__main__":
    sys.stdout.write("\033]0;STATS\007")
    sys.stdout.flush()
    make_stats.main()
    read_stats.main()
