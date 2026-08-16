# -*- coding: UTF-8 -*-
import default

if __name__ == "__main__":
    if len(sys.argv) > 2:
        default.router(sys.argv[2][1:])
    else:
        default.main_menu()
