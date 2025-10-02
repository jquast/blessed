from blessed import Terminal, DecPrivateMode

DEC_MODE = DecPrivateMode.BRACKETED_PASTE


def main():
    """Interactive test for bracketed paste mode."""
    term = Terminal()
    print("Checking status of bracketed paste: ", end='', flush=True)
    with term.cbreak():
        response = term.get_dec_mode(DEC_MODE, timeout=1.0)

    # flush input
    while term.inkey(timeout=0):
        pass

    if response.is_supported():
        print('supported, currently ', end='')
        if response.is_enabled():
            print("enabled ", end='')
        else:
            print("disabled ", end='')
        if response.is_permanent():
            exit(1)
            print('permanently (cannot be changed!)')
        else:
            print('temporarily (can be changed)')
    elif response.is_failed():
        print("This terminal is not DEC Private Mode capable!")
    else:
        print("Not supported.")

    print(term.home + term.clear)
    print(term.reverse("Testing Bracketed Paste Mode".center(term.width)))
    print("Try pasting some text (Ctrl+V). Press 'q' to quit.\n")

    with term.raw(), term.dec_modes_enabled(DEC_MODE, timeout=1.0):
        while True:
            key = term.inkey()
            if key.lower() == 'q':
                break
            if key.mode == DEC_MODE:
                print(repr(key.mode_values()), end='\r\n')
            else:
                print(repr(str(key)), key.name, end='\r\n')


if __name__ == '__main__':
    main()
