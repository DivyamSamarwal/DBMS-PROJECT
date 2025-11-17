import traceback
import sys
from pathlib import Path
# Ensure project root is on sys.path so tests package can be imported
proj_root = str(Path(__file__).resolve().parents[1])
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

import tests.test_borrower_flow as tb

def run():
    print('Setting up test module...')
    try:
        tb.setup_module(None)
    except Exception:
        print('setup_module failed:')
        traceback.print_exc()
        return 2

    try:
        print('Running test_create_borrower_and_delete_flow...')
        tb.test_create_borrower_and_delete_flow()
    except AssertionError:
        print('Test failed:')
        traceback.print_exc()
        try:
            tb.teardown_module(None)
        except Exception:
            pass
        return 1
    except Exception:
        print('Test raised exception:')
        traceback.print_exc()
        try:
            tb.teardown_module(None)
        except Exception:
            pass
        return 1

    print('Test passed. Tearing down...')
    try:
        tb.teardown_module(None)
    except Exception:
        print('teardown_module failed:')
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    exit_code = run()
    raise SystemExit(exit_code)
