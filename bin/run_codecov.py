"""Workaround for https://github.com/codecov/codecov-python/issues/158."""
# std imports
import sys

# 3rd party
import codecov
import tenacity

tenacity.retry(wait=tenacity.wait_random(min=1, max=5),
               stop=tenacity.stop_after_delay(60))
def main():
    """Run codecov up to RETRIES times On the final attempt, let it exit normally."""

    # Make a copy of argv and make sure --required is in it
    args = sys.argv[1:]
    if '--required' not in args:
        args.append('--required')
    codecov.main(*args)


if __name__ == '__main__':
    main()
