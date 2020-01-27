# Workaround for https://github.com/codecov/codecov-python/issues/158

import sys

import codecov


RETRIES = 5


def main():

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
            if not err.code:
                sys.exit(err.code)


if __name__ == '__main__':
    main()