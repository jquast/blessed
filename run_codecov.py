"""
Workaround for https://github.com/codecov/codecov-python/issues/158
"""

import sys
import time

import codecov


RETRIES = 5
TIMEOUT = 2


def main():
    """
    Run codecov up to RETRIES times
    On the final attempt, let it exit normally
    """

    # Make a copy of argv and make sure --required is in it
    args = sys.argv[1:]
    if '--required' not in args:
        args.append('--required')

    for num in range(1, RETRIES + 1):

        print('Running codecov attempt %d: ' % num)
        # On the last, let codecov handle the exit
        if num == RETRIES:
            codecov.main()

        try:
            codecov.main(*args)
        except SystemExit as err:
            # If there's no exit code, it was successful
            if err.code:
                time.sleep(TIMEOUT)
            else:
                sys.exit(err.code)
        else:
            break


if __name__ == '__main__':
    main()
