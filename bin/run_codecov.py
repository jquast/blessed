"""Workaround for https://github.com/codecov/codecov-python/issues/158."""
# std imports
import sys

# 3rd party
import codecov
import tenacity

tenacity.retry(wait=tenacity.wait_random(min=1, max=5),
               stop=tenacity.stop_after_delay(60))
def main():
    codecov.main(sys.argv[1:])


if __name__ == '__main__':
    main()
